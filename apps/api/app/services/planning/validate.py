"""validate_itinerary：模型排出来的行程，给用户看之前先用结构化数据校验。

这是一个纯函数：输入行程草稿、景点库、程序查到的真实交通、用户要求和"今天"，输出错误和警告。
不调用模型，不联网，所以可以用单元测试把每条规则都测到（tests/test_validate_itinerary.py）。

两级：
- 错误：行程不能照着走（景点不存在、闭馆、时间重叠、交通时间不够……）。有一条错误就是"未通过"。
- 警告：行程能走，但有的地方没法确认（开放时间未知、日期未定、数据过期或待确认……）。
  没有错误、有警告时是"有警告"；两样都没有才是"通过"。

数据缺失时的原则：资料没写不等于闭馆，所以算警告"无法校验"，不算错误；但也不能算通过。

规则和数值的说明见 docs/architecture/ai-planning-pipeline.md，数值由 Cecilia 在 2026-11-15 确认。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, timedelta

from app.data_quality.rules import FIELD_LABELS
from app.schemas.planning import PlanDraft, PlanStop, TripFrame, ValidationIssue, ValidationReport
from app.schemas.poi import Fact, OpeningHours, OpeningPeriod, PoiFile
from app.schemas.route import RouteOut

# 每天从第一站到达到最后一站离开，最多多少分钟
DAY_LIMIT_MINUTES = {"relaxed": 8 * 60, "moderate": 10 * 60, "intensive": 12 * 60}
PACE_LABELS = {"relaxed": "轻松", "moderate": "适中", "intensive": "紧凑"}
# 每天最早到达第一站、最晚离开最后一站
DAY_EARLIEST = 8 * 60
DAY_LATEST = 22 * 60
# 空档比真实交通时间多出不到这么多分钟，给"偏紧"警告（换乘、找入口、排队安检）
TRANSPORT_SLACK_MINUTES = 10
# 停留时间少于建议时长的这个比例，给"停留偏短"警告
SHORT_STAY_RATIO = 0.5

WEEKDAY_LABELS = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}

# 行程卡上用到的资料：查它们有没有过期、是不是待确认
USED_FACTS = ("openingHours", "recommendedDurationMinutes", "reservation", "ticket", "payment")

_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")

Legs = Mapping[tuple[str, str], RouteOut | None]


def parse_hhmm(value: str) -> int | None:
    """"09:30" → 570。格式不对返回 None。"""
    m = _TIME.match(value.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return h * 60 + mi


def fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def day_date(frame: TripFrame, day_number: int) -> date | None:
    if frame.startDate is None:
        return None
    return frame.startDate + timedelta(days=day_number - 1)


class _Collector:
    def __init__(self) -> None:
        self.issues: list[ValidationIssue] = []

    def error(self, code: str, message: str, **kw: object) -> None:
        self.issues.append(ValidationIssue(level="error", code=code, message=message, **kw))  # type: ignore[arg-type]

    def warn(self, code: str, message: str, **kw: object) -> None:
        self.issues.append(ValidationIssue(level="warning", code=code, message=message, **kw))  # type: ignore[arg-type]


def validate_itinerary(
    draft: PlanDraft,
    *,
    pois: Mapping[str, PoiFile],
    legs: Legs,
    frame: TripFrame,
    today: date,
) -> ValidationReport:
    """校验一份行程。

    - `pois`：景点库，id → 景点资料。
    - `legs`：同一天相邻两站之间程序查到的真实交通，(起点 id, 终点 id) → 路线；查不到时为 None 或缺这一项。
    - `frame`：用户要求的天数、开始日期（可以未定）、节奏。
    - `today`：武汉时间的今天，用来判断资料有没有过期。
    """
    c = _Collector()

    # ---------- 整份行程 ----------
    if len(draft.days) != frame.days:
        c.error("day-count", f"要求 {frame.days} 天，行程排了 {len(draft.days)} 天。")
    for index, day in enumerate(draft.days, start=1):
        if day.dayNumber != index:
            c.error("day-number", f"第 {index} 个日程的编号写成了第 {day.dayNumber} 天，应该从 1 开始按顺序编号。", dayNumber=day.dayNumber)

    if frame.startDate is None:
        c.warn("date-unknown", "旅行日期还没定，闭馆日没法校验。")

    seen: dict[str, int] = {}
    for day in draft.days:
        for stop in day.stops:
            if stop.poiId in seen and stop.poiId in pois:
                c.error(
                    "duplicate-poi",
                    f"{pois[stop.poiId].name}安排了两次（第 {seen[stop.poiId]} 天和第 {day.dayNumber} 天）。",
                    dayNumber=day.dayNumber,
                    poiId=stop.poiId,
                )
            seen.setdefault(stop.poiId, day.dayNumber)

    # ---------- 每一天 ----------
    for day in draft.days:
        d = day.dayNumber
        when = day_date(frame, d)
        if not day.stops:
            c.error("empty-day", f"第 {d} 天一个景点都没有。", dayNumber=d)
            continue

        times: list[tuple[int, int] | None] = []
        for stop in day.stops:
            times.append(_check_stop(c, stop, d, when, pois, frame))

        _check_transport(c, day.stops, times, d, pois, legs)
        _check_day_span(c, times, d, frame)

    # ---------- 用到的资料过期或待确认 ----------
    for poi_id in seen:
        poi = pois.get(poi_id)
        if poi is not None:
            _check_data(c, poi, seen[poi_id], today)

    errors = any(i.level == "error" for i in c.issues)
    status = "failed" if errors else ("warning" if c.issues else "passed")
    return ValidationReport(status=status, issues=c.issues)


# ---------- 一站 ----------


def _check_stop(
    c: _Collector,
    stop: PlanStop,
    d: int,
    when: date | None,
    pois: Mapping[str, PoiFile],
    frame: TripFrame,
) -> tuple[int, int] | None:
    """检查一站，返回 (到达, 离开) 的分钟数；时间格式不对返回 None。"""
    poi = pois.get(stop.poiId)
    if poi is None:
        c.error("unknown-poi", f"第 {d} 天的景点 id「{stop.poiId}」不在候选景点里（只能从景点库给出的候选里选）。", dayNumber=d, poiId=stop.poiId)

    name = poi.name if poi else stop.poiId
    arrive, leave = parse_hhmm(stop.arrive), parse_hhmm(stop.leave)
    if arrive is None or leave is None:
        bad = stop.arrive if arrive is None else stop.leave
        c.error("bad-time", f"第 {d} 天{name}的时间「{bad}」格式不对，应该是 HH:MM。", dayNumber=d, poiId=stop.poiId)
        return None
    if leave <= arrive:
        c.error(
            "time-order",
            f"第 {d} 天{name}的离开时间 {stop.leave} 不晚于到达时间 {stop.arrive}。",
            dayNumber=d,
            poiId=stop.poiId,
        )
        return None

    if poi is not None:
        _check_opening(c, poi, arrive, leave, d, when)
        _check_stay(c, poi, arrive, leave, d)
    return arrive, leave


def _matching_periods(hours: OpeningHours, when: date) -> list[OpeningPeriod]:
    wd = when.isoweekday()
    return [p for p in hours.periods if wd in p.weekdays and (not p.months or when.month in p.months)]


def _check_opening(c: _Collector, poi: PoiFile, arrive: int, leave: int, d: int, when: date | None) -> None:
    kw = {"dayNumber": d, "poiId": poi.id, "fields": ["openingHours"]}
    fact: Fact[OpeningHours] | None = poi.openingHours
    hours = fact.value if fact is not None and fact.verification != "todo" else None
    if hours is None:
        c.warn("hours-unknown", f"{poi.name}的开放时间未知，无法校验第 {d} 天的安排。", **kw)
        return
    if hours.allDay:
        return

    note = f"（备注：{hours.note}）" if hours.note else ""
    if when is None:
        # 日期未定：每天时段都一样的，照样查时间；有固定闭馆日的提醒一句
        if hours.closedWeekdays:
            days = "、".join(WEEKDAY_LABELS[w] for w in sorted(hours.closedWeekdays))
            c.warn("closed-day-unchecked", f"{poi.name}{days}闭馆，日期未定，没法确认第 {d} 天是不是闭馆日。{note}", **kw)
        distinct = {(p.open, p.close, p.lastEntry) for p in hours.periods}
        if len(distinct) != 1:
            c.warn("hours-unknown", f"{poi.name}不同日子开放时间不一样，日期未定，无法校验第 {d} 天的时间。", **kw)
            return
        periods = hours.periods[:1]
    else:
        wd = when.isoweekday()
        if wd in hours.closedWeekdays:
            c.error(
                "closed-day",
                f"第 {d} 天（{when.isoformat()}，{WEEKDAY_LABELS[wd]}）{poi.name}闭馆。{note}",
                **kw,
            )
            return
        periods = _matching_periods(hours, when)
        if not periods:
            c.warn(
                "hours-unknown",
                f"资料里没有{poi.name}在 {when.month} 月{WEEKDAY_LABELS[wd]}的开放时间，无法校验第 {d} 天的安排。{note}",
                **kw,
            )
            return

    problems_by_period = [_period_problems(p, arrive, leave) for p in periods]
    if any(not probs for probs in problems_by_period):
        return  # 有一个时段完全合适
    # 都不合适：按问题最少的那个时段报（例如中午闭馆时，报"下午还没开门"而不是"上午已关门"）
    for code, message in min(problems_by_period, key=len):
        c.error(code, f"第 {d} 天{poi.name}：{message}{note}", **kw)


def _period_problems(p: OpeningPeriod, arrive: int, leave: int) -> list[tuple[str, str]]:
    open_, close = parse_hhmm(p.open), parse_hhmm(p.close)
    last = parse_hhmm(p.lastEntry) if p.lastEntry else None
    problems: list[tuple[str, str]] = []
    if open_ is not None and arrive < open_:
        problems.append(("before-open", f"{fmt(arrive)} 到达，还没开门（{p.open} 开门）。"))
    if last is not None and arrive > last:
        problems.append(("after-last-entry", f"{fmt(arrive)} 到达，已经过了最晚入场时间 {p.lastEntry}。"))
    elif last is None and close is not None and arrive >= close:
        problems.append(("after-last-entry", f"{fmt(arrive)} 到达，已经关门了（{p.close} 关门）。"))
    if close is not None and leave > close:
        problems.append(("after-close", f"{fmt(leave)} 离开，晚于关门时间 {p.close}。"))
    return problems


def _check_stay(c: _Collector, poi: PoiFile, arrive: int, leave: int, d: int) -> None:
    kw = {"dayNumber": d, "poiId": poi.id, "fields": ["recommendedDurationMinutes"]}
    fact = poi.recommendedDurationMinutes
    rec = fact.value if fact is not None and fact.verification != "todo" else None
    if rec is None:
        c.warn("duration-unknown", f"{poi.name}没有建议游玩时长，第 {d} 天停留 {leave - arrive} 分钟够不够没法判断。", **kw)
        return
    if leave - arrive < rec * SHORT_STAY_RATIO:
        c.warn("stay-short", f"第 {d} 天{poi.name}只停留 {leave - arrive} 分钟，建议游玩 {rec} 分钟。", **kw)


# ---------- 相邻两站 ----------


def _check_transport(
    c: _Collector,
    stops: list[PlanStop],
    times: list[tuple[int, int] | None],
    d: int,
    pois: Mapping[str, PoiFile],
    legs: Legs,
) -> None:
    for i in range(1, len(stops)):
        prev, nxt = stops[i - 1], stops[i]
        pt, nt = times[i - 1], times[i]
        a = pois[prev.poiId].name if prev.poiId in pois else prev.poiId
        b = pois[nxt.poiId].name if nxt.poiId in pois else nxt.poiId
        kw = {"dayNumber": d, "poiId": nxt.poiId}
        if pt is None or nt is None:
            continue  # 时间格式错已经报过
        gap = nt[0] - pt[1]
        if gap < 0:
            c.error("overlap", f"第 {d} 天{b} {fmt(nt[0])} 到达，比离开{a}的 {fmt(pt[1])} 还早，时间重叠。", **kw)
            continue
        if prev.poiId not in pois or nxt.poiId not in pois:
            continue  # 景点不存在已经报过，查不了路线
        route = legs.get((prev.poiId, nxt.poiId))
        if route is None or route.status != "ok" or route.durationMinutes is None:
            why = f"（{route.error.message}）" if route is not None and route.error else ""
            c.warn("route-unknown", f"第 {d} 天{a}到{b}的交通时间没查到，无法校验空档 {gap} 分钟够不够。{why}", **kw)
            continue
        need = route.durationMinutes
        mode = {"walk": "步行", "transit": "公交地铁", "drive": "驾车"}[route.mode]
        if gap < need:
            c.error(
                "transport-too-short",
                f"第 {d} 天{a}到{b}{mode}要 {need} 分钟，行程只留了 {gap} 分钟。",
                **kw,
            )
        elif gap < need + TRANSPORT_SLACK_MINUTES:
            c.warn(
                "transport-tight",
                f"第 {d} 天{a}到{b}{mode}要 {need} 分钟，只留了 {gap} 分钟，余量不到 {TRANSPORT_SLACK_MINUTES} 分钟。",
                **kw,
            )
        if route.cache == "stale":
            c.warn(
                "route-stale",
                f"第 {d} 天{a}到{b}的交通时间用的是过期的缓存（{route.warning or '重新查询失败'}）。",
                **kw,
            )


def _check_day_span(c: _Collector, times: list[tuple[int, int] | None], d: int, frame: TripFrame) -> None:
    valid = [t for t in times if t is not None]
    if not valid:
        return
    start, end = min(t[0] for t in valid), max(t[1] for t in valid)
    if start < DAY_EARLIEST:
        c.error("day-window", f"第 {d} 天 {fmt(start)} 就开始，早于 {fmt(DAY_EARLIEST)}。", dayNumber=d)
    if end > DAY_LATEST:
        c.error("day-window", f"第 {d} 天到 {fmt(end)} 才结束，晚于 {fmt(DAY_LATEST)}。", dayNumber=d)
    limit = DAY_LIMIT_MINUTES[frame.pace]
    if end - start > limit:
        hours = (end - start) / 60
        c.error(
            "day-too-long",
            f"第 {d} 天从 {fmt(start)} 到 {fmt(end)}，共 {hours:.1f} 小时，超过{PACE_LABELS[frame.pace]}节奏的上限 {limit // 60} 小时。",
            dayNumber=d,
        )


# ---------- 资料 ----------


def _check_data(c: _Collector, poi: PoiFile, d: int, today: date) -> None:
    pending: list[str] = []
    missing: list[str] = []
    pending_fields: list[str] = []
    missing_fields: list[str] = []
    for field in USED_FACTS:
        fact = getattr(poi, field)
        label = FIELD_LABELS[field]
        if fact is None or fact.verification == "todo":
            # 开放时间和建议时长缺了，上面已经各报过一条"无法校验"
            if field not in ("openingHours", "recommendedDurationMinutes"):
                missing.append(label)
                missing_fields.append(field)
            continue
        if fact.expiresAt is not None and fact.expiresAt < today:
            c.warn(
                "data-expired",
                f"{poi.name}的{label}已经过期（有效期到 {fact.expiresAt.isoformat()}），行程依据的可能不是现在的情况。",
                dayNumber=d,
                poiId=poi.id,
                fields=[field],
            )
        elif fact.verification == "placeholder":
            pending.append(label)
            pending_fields.append(field)
    if pending:
        c.warn(
            "data-pending",
            f"{poi.name}的{'、'.join(pending)}是占位资料，待确认。",
            dayNumber=d,
            poiId=poi.id,
            fields=pending_fields,
        )
    if missing:
        c.warn(
            "data-missing",
            f"{poi.name}的{'、'.join(missing)}还没有资料，行程卡上会写“待补充”。",
            dayNumber=d,
            poiId=poi.id,
            fields=missing_fields,
        )
