"""方案的数字、"几乎一样"的判断和方案之间的比较表（板块 5B）。

全部由程序算，不调用模型，也不再查景点库和高德：数字从保存下来的行程快照（ItineraryVersionData）里来，
同一个版本什么时候算结果都一样。

规则（2026-11-15 Cecilia 定）：
- 交通时间：只加查到了的段，再按步行、公交地铁、打车分开；没查到的段数单独写出来，不猜。
- 步行距离：步行段的距离 + 公交地铁段里换乘、进出站要走的距离（高德的 walking_distance）；打车算 0。
  旧缓存里没有换乘步行距离的段记为"不详"，由路线预热脚本从缓存的原始返回里补。
- 门票：每人、成人日场全票；免费入园的算 0（园内另收费的观光车、游船不算）。19:00 以后到达、资料里有夜场票的按夜场；
  夜场按星期几分价钱的，日期未定就写"120 或 150 元"这种范围。资料里没有票价的写"不详"，总价标"不完整"。
- 几乎一样：两份用到的景点只差 0 或 1 个（一份比另一份多出来的景点不超过 1 个），并且每天结束时间都相差不到 1 小时。
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.schemas.itinerary import (
    ComparisonRow,
    DayMetrics,
    ItineraryDay,
    ItineraryStop,
    ItineraryVersionData,
    PlanComparison,
    PlanMetrics,
    StopTicket,
)
from app.schemas.planning import PlanDraft
from app.schemas.poi import TicketItem
from app.services.planning.validate import parse_hhmm

NIGHT_FROM = 19 * 60
# 名字里带这些字的不是成人全价票
NOT_ADULT_FULL = ("半票", "优惠", "学生", "儿童", "老人", "长者", "免票")
NEAR_DUPLICATE_END_MINUTES = 60
NEAR_DUPLICATE_PLACES = 1

MODE_ORDER = ("walk", "transit", "drive")
MODE_LABELS = {"walk": "步行", "transit": "公交地铁", "drive": "打车"}
_WEEKDAY_CHARS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:.1f}"


# ---------- 门票 ----------


def _weekdays_in(name: str) -> set[int] | None:
    """从票名里读出适用的星期，例如"周五至周日" → {5, 6, 7}。读不出来返回 None。"""
    found: set[int] = set()
    for a, b in re.findall(r"周([一二三四五六日天])\s*[至到\-—~]\s*周?([一二三四五六日天])", name):
        lo, hi = _WEEKDAY_CHARS[a], _WEEKDAY_CHARS[b]
        found |= set(range(lo, hi + 1)) if lo <= hi else set(range(lo, 8)) | set(range(1, hi + 1))
    if not found:
        found = {_WEEKDAY_CHARS[c] for c in re.findall(r"周([一二三四五六日天])", name)}
    return found or None


def _adult(items: list[TicketItem]) -> list[TicketItem]:
    return [i for i in items if not any(w in i.name for w in NOT_ADULT_FULL)]


def stop_ticket(stop: ItineraryStop, day: ItineraryDay) -> StopTicket:
    base = {"dayNumber": day.dayNumber, "poiId": stop.poiId, "name": stop.name}
    fact = stop.facts.ticket
    unknown = StopTicket(**base, minCny=None, maxCny=None, label="不详")
    if fact.status == "missing" or fact.value is None:
        return unknown
    if fact.value.free:
        return StopTicket(**base, minCny=0, maxCny=0, label="免费")

    night = _adult([i for i in fact.value.items if "夜场" in i.name])
    day_items = _adult([i for i in fact.value.items if "夜场" not in i.name])
    arrive = parse_hhmm(stop.arrive)
    if arrive is not None and arrive >= NIGHT_FROM and night:
        chosen = night
        undecided = ""
        if day.date is not None:
            wd = day.date.isoweekday()
            matching = [i for i in night if (w := _weekdays_in(i.name)) is not None and wd in w]
            if matching:
                chosen = matching
        else:
            undecided = "（日期未定）" if len({i.priceCny for i in night}) > 1 else ""
        lo, hi = min(i.priceCny for i in chosen), max(i.priceCny for i in chosen)
        price = f"{_num(lo)} 元" if lo == hi else f"{_num(lo)} 或 {_num(hi)} 元"
        return StopTicket(**base, minCny=lo, maxCny=hi, label=f"夜场成人票 {price}{undecided}")
    if day_items:
        item = day_items[0]
        return StopTicket(**base, minCny=item.priceCny, maxCny=item.priceCny, label=f"{item.name} {_num(item.priceCny)} 元")
    return unknown


# ---------- 一份方案的数字 ----------


def _walking(leg_route_mode: str, distance: int | None, walking: int | None) -> int | None:
    if leg_route_mode == "walk":
        return walking if walking is not None else distance
    if leg_route_mode == "transit":
        return walking
    return 0


def _day_metrics(day: ItineraryDay, by_mode: dict[str, int]) -> tuple[DayMetrics, int]:
    """返回这天的数字和没查到的段数。"""
    leaves = [t for t in (parse_hhmm(s.leave) for s in day.stops) if t is not None]
    pairs = max(len(day.stops) - 1, 0)
    known = [leg for leg in day.legs if leg.route.status == "ok" and leg.route.durationMinutes is not None]
    walking_known = 0
    walking_m = 0
    for leg in known:
        r = leg.route
        by_mode[r.mode] = by_mode.get(r.mode, 0) + (r.durationMinutes or 0)
        w = _walking(r.mode, r.distanceMeters, r.walkingDistanceMeters)
        if w is not None:
            walking_known += 1
            walking_m += w
    end = max(leaves) if leaves else None
    metrics = DayMetrics(
        dayNumber=day.dayNumber,
        stopCount=len(day.stops),
        end=f"{end // 60:02d}:{end % 60:02d}" if end is not None else None,
        transportMinutes=sum(leg.route.durationMinutes or 0 for leg in known),
        walkingMeters=walking_m,
        walkingUnknownLegs=pairs - walking_known,
    )
    return metrics, pairs - len(known)


def plan_metrics(v: ItineraryVersionData) -> PlanMetrics:
    by_mode: dict[str, int] = {m: 0 for m in MODE_ORDER}
    days: list[DayMetrics] = []
    unknown = 0
    for day in v.days:
        dm, u = _day_metrics(day, by_mode)
        days.append(dm)
        unknown += u

    tickets = [stop_ticket(s, d) for d in v.days for s in d.stops]
    stops = [s for d in v.days for s in d.stops]
    report = v.validation
    return PlanMetrics(
        poiIds=[s.poiId for s in stops],
        poiNames=[s.name for s in stops],
        stopCount=len(stops),
        transportMinutes=sum(d.transportMinutes for d in days),
        minutesByMode=by_mode,
        unknownLegs=unknown,
        walkingMeters=sum(d.walkingMeters for d in days),
        walkingUnknownLegs=sum(d.walkingUnknownLegs for d in days),
        tickets=tickets,
        ticketMinCny=float(sum(t.minCny for t in tickets if t.minCny is not None)),
        ticketMaxCny=float(sum(t.maxCny for t in tickets if t.maxCny is not None)),
        ticketComplete=all(t.minCny is not None for t in tickets),
        validationStatus=report.status,
        errorCount=sum(1 for i in report.issues if i.level == "error"),
        warningCount=sum(1 for i in report.issues if i.level == "warning"),
        rounds=v.planner.rounds,
        days=days,
    )


# ---------- 几乎一样 ----------


def near_duplicate(a: PlanDraft, b: PlanDraft) -> str | None:
    """两份草稿几乎一样时返回原因（给用户看的话），不一样返回 None。只看景点 id 和时间，不看理由。"""
    if len(a.days) != len(b.days):
        return None
    pa = {s.poiId for d in a.days for s in d.stops}
    pb = {s.poiId for d in b.days for s in d.stops}
    diff = max(len(pa - pb), len(pb - pa))
    if diff > NEAR_DUPLICATE_PLACES:
        return None
    for da, db in zip(a.days, b.days):
        ea = max((t for t in (parse_hhmm(s.leave) for s in da.stops) if t is not None), default=None)
        eb = max((t for t in (parse_hhmm(s.leave) for s in db.stops) if t is not None), default=None)
        if ea is None or eb is None:
            if ea != eb:
                return None
            continue
        if abs(ea - eb) >= NEAR_DUPLICATE_END_MINUTES:
            return None
    places = "用到的景点相同" if diff == 0 else f"用到的景点只差 {diff} 个"
    return f"{places}，每天结束时间相差不到 1 小时"


# ---------- 比较表 ----------


def _distance(meters: int) -> str:
    return f"{meters} 米" if meters < 1000 else f"{_num(round(meters / 1000, 1))} 公里"


def _ticket_text(m: PlanMetrics) -> str:
    lo, hi = m.ticketMinCny, m.ticketMaxCny
    text = f"{_num(lo)} 元" if lo == hi else f"{_num(lo)} 或 {_num(hi)} 元"
    if not m.ticketComplete:
        names = "、".join(t.name for t in m.tickets if t.minCny is None)
        text += f"（不完整：{names} 票价不详）"
    return text


def _validation_text(m: PlanMetrics) -> str:
    if m.validationStatus == "passed":
        return "通过"
    head = "有警告" if m.validationStatus == "warning" else "未通过"
    return f"{head}：{m.errorCount} 条错误、{m.warningCount} 条警告"


def compare_plans(labels: Sequence[str], plans: Sequence[ItineraryVersionData]) -> PlanComparison:
    assert len(labels) == len(plans)
    ms = [p.metrics or plan_metrics(p) for p in plans]

    def row(key: str, label: str, texts: list[str], values: list[float | None] | None = None, note: str | None = None) -> ComparisonRow:
        return ComparisonRow(key=key, label=label, texts=texts, values=values or [None] * len(ms), note=note)

    rows = [
        row("places", "用了哪些景点", ["、".join(m.poiNames) or "—" for m in ms]),
        row("stopCount", "景点数", [f"{m.stopCount} 个" for m in ms], [float(m.stopCount) for m in ms]),
        row(
            "transportMinutes",
            "交通时间合计",
            [f"{m.transportMinutes} 分钟" + (f"（{m.unknownLegs} 段没查到）" if m.unknownLegs else "") for m in ms],
            [float(m.transportMinutes) for m in ms],
            note="高德查到的时间，没查到的段没算进去",
        ),
        row(
            "byMode",
            "其中",
            ["、".join(f"{MODE_LABELS[k]} {m.minutesByMode.get(k, 0)} 分钟" for k in MODE_ORDER if m.minutesByMode.get(k)) or "—" for m in ms],
        ),
        row(
            "walkingMeters",
            "步行距离",
            [_distance(m.walkingMeters) + (f"（{m.walkingUnknownLegs} 段不详）" if m.walkingUnknownLegs else "") for m in ms],
            [float(m.walkingMeters) for m in ms],
            note="站与站之间：步行段的距离加公交地铁换乘、进出站的步行，不含景点里面走的路",
        ),
        row(
            "tickets",
            "门票（每人）",
            [_ticket_text(m) for m in ms],
            [m.ticketMinCny for m in ms],
            note="成人日场全票，免费的算 0，园内另收费的项目不算；19:00 以后到达按夜场",
        ),
    ]
    for n in range(1, max((len(m.days) for m in ms), default=0) + 1):
        texts = []
        for m in ms:
            day = next((d for d in m.days if d.dayNumber == n), None)
            texts.append(day.end if day is not None and day.end is not None else "—")
        rows.append(row(f"end-day-{n}", f"第 {n} 天几点结束", texts))
    rows.append(row("validation", "校验", [_validation_text(m) for m in ms], [float(m.errorCount) for m in ms]))
    return PlanComparison(labels=list(labels), rows=rows)
