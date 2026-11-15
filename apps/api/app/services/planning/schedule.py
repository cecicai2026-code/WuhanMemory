"""把模型排的行程（每天出发时间、站点顺序、每站停留多久）推成带钟点的行程（板块 6C）。

规则（2026-11-15 Cecilia 定）：
1. 第一站到达 = 这天的出发时间。
2. 后面每站到达 = 上一站离开 + 真实交通时间（程序向高德查的，和校验用的同一段）+ 10 分钟余量。
3. 到达时间往后取整到 5 分钟（只往后，不往前，所以余量只会多于 10 分钟）。
4. 推出来的到达早于开门：等到开门再进（中间的空档就是等待）。资料里开放时间未知的不等。
5. 离开 = 到达 + 停留时长。
6. 相邻两站的交通没查到（高德出错）：这段排不出时间，记一条错误 transport-unknown，这份不展示。
7. 推过了午夜：这天排不下，记一条错误 day-overflow，后面的站不再推。
8. 推不出钟点的站：钟点留空、标 scheduled=False，校验跳过它们的时间检查（原因已经是第 6、7 条的错误）。

纯函数，不调用模型、不联网。推完的行程照常交给 validate_itinerary 查开放时间、最晚入场、闭馆日、每天总时长、侧重规则。
"""

from __future__ import annotations

from collections.abc import Mapping

from app.schemas.planning import OutlineStop, PlanDay, PlanDraft, PlanOutline, PlanStop, TripFrame, ValidationIssue
from app.core.lang import L
from app.schemas.poi import PoiFile
from app.services.poi_i18n import display_name
from app.schemas.route import RouteOut
from app.services.planning.validate import TRANSPORT_SLACK_MINUTES, _matching_periods, day_date, fmt, parse_hhmm

ROUND_TO = 5
MIDNIGHT = 24 * 60
# 推不出时间的站：钟点留空、标 scheduled=False（同一天已经有一条错误说明原因）

Legs = Mapping[tuple[str, str], RouteOut | None]


def _unscheduled(s: OutlineStop) -> PlanStop:
    return PlanStop(poiId=s.poiId, arrive="", leave="", reason=s.reason, scheduled=False)


def _round_up(minutes: int) -> int:
    return -(-minutes // ROUND_TO) * ROUND_TO


def _opening_wait(poi: PoiFile | None, arrive: int, frame: TripFrame, day_number: int) -> int:
    """到得太早就等到开门。返回调整后的到达时间。"""
    if poi is None or poi.openingHours is None or poi.openingHours.verification == "todo":
        return arrive
    hours = poi.openingHours.value
    if hours is None or hours.allDay:
        return arrive
    when = day_date(frame, day_number)
    if when is None:
        # 日期未定：每天时段都一样才知道几点开门
        if len({(p.open, p.close, p.lastEntry) for p in hours.periods}) != 1:
            return arrive
        periods = hours.periods[:1]
    else:
        if when.isoweekday() in hours.closedWeekdays:
            return arrive  # 闭馆日交给校验报错
        periods = _matching_periods(hours, when)
    spans = sorted(
        (o, c) for o, c in ((parse_hhmm(p.open), parse_hhmm(p.close)) for p in periods) if o is not None
    )
    for open_, close in spans:
        if close is not None and arrive >= close:
            continue
        return max(arrive, open_)
    return arrive


def schedule(
    outline: PlanOutline,
    *,
    pois: Mapping[str, PoiFile],
    legs: Legs,
    frame: TripFrame,
) -> tuple[PlanDraft, list[ValidationIssue]]:
    """返回推好钟点的行程和排时间时发现的错误（交通没查到、出发时间格式错、过了午夜）。"""
    issues: list[ValidationIssue] = []
    days: list[PlanDay] = []
    for day in outline.days:
        d = day.dayNumber
        stops: list[PlanStop] = []
        start = parse_hhmm(day.start)
        if start is None:
            issues.append(ValidationIssue(level="error", code="bad-time", dayNumber=d,
                                          message=L(f"第 {d} 天的出发时间「{day.start}」格式不对，应该是 HH:MM。",
                                                    f"The start time \"{day.start}\" on day {d} is not in HH:MM format.")))
            stops = [_unscheduled(s) for s in day.stops]
            days.append(PlanDay(dayNumber=d, theme=day.theme, stops=stops))
            continue

        clock: int | None = None  # 上一站离开的时间
        stuck = False
        for i, s in enumerate(day.stops):
            if stuck:
                stops.append(_unscheduled(s))
                continue
            if i == 0 or clock is None:
                arrive = start
            else:
                prev = day.stops[i - 1]
                travel = 0
                if prev.poiId in pois and s.poiId in pois and prev.poiId != s.poiId:
                    route = legs.get((prev.poiId, s.poiId))
                    if route is None or route.status != "ok" or route.durationMinutes is None:
                        why = L(f"（{route.error.message}）", f" ({route.error.message})") if route is not None and route.error else ""
                        a, b = display_name(pois[prev.poiId]), display_name(pois[s.poiId])
                        issues.append(ValidationIssue(
                            level="error", code="transport-unknown", dayNumber=d, poiId=s.poiId,
                            message=L(f"第 {d} 天{a}到{b}的交通没查到，没法排后面的时间。{why}",
                                      f"No route was found from {a} to {b} on day {d}, so the rest of the day can't be timed.{why}"),
                        ))
                        stuck = True
                        stops.append(_unscheduled(s))
                        continue
                    travel = route.durationMinutes
                # 景点不存在、重复的段没有路线：校验会报错，这里只加余量
                arrive = clock + travel + TRANSPORT_SLACK_MINUTES
            arrive = _opening_wait(pois.get(s.poiId), _round_up(arrive), frame, d)
            leave = arrive + s.stayMinutes
            if leave >= MIDNIGHT:
                name = display_name(pois[s.poiId]) if s.poiId in pois else s.poiId
                issues.append(ValidationIssue(
                    level="error", code="day-overflow", dayNumber=d, poiId=s.poiId,
                    message=L(
                        f"第 {d} 天从 {fmt(start)} 出发，按停留时长和真实交通推下来，到{name}已经过了午夜，这天排不下这么多站或停留太久。",
                        f"Starting at {fmt(start)} on day {d}, the stays and real travel times push {name} past midnight; the day can't fit this many stops or such long stays.",
                    ),
                ))
                stuck = True
                stops.append(_unscheduled(s))
                continue
            stops.append(PlanStop(poiId=s.poiId, arrive=fmt(arrive), leave=fmt(leave), reason=s.reason))
            clock = leave
        days.append(PlanDay(dayNumber=d, theme=day.theme, stops=stops))
    return PlanDraft(title=outline.title, days=days), issues
