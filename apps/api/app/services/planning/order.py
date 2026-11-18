"""每天站点的顺序由程序按真实交通时间重排（2026-11-18 Cecilia 定，ADR 0010）。

模型决定每天去哪几站、每站待多久、几点出发；程序在每一天内部把这些站重新排列，
让相邻两站之间的真实交通时间（和推钟点、校验用的是同一段高德路线）加起来最少。

规则：
1. 只在同一天内部换顺序，不把站挪到别的天，不增删站。
2. 第一站不固定：不知道用户住哪，按"开放路径"算（不回到起点）。出发时间沿用模型给的，表示到达第一站的时间。
3. 要最小化的是这一天的总交通分钟数（相邻两站之间）。
4. 新顺序的错误不能比模型的顺序多：按交通时间从少到多试，第一个"这一天的错误数不多于模型顺序"的就是答案。
   错误数由调用方给的 day_errors 算（推钟点 + validate_itinerary + 侧重规则里属于这一天的错误）。
5. 交通时间和模型的顺序一样或更多：保留模型的顺序（不为换而换）。
6. 不重排的情况：一天少于 2 站；有景点不在候选里或同一站出现两次（校验会报错）；
   模型顺序里有一段交通没查到（没法比较）；一天超过 MAX_STOPS 站（穷举太多）。
   别的顺序里有没查到的段，这个顺序就不考虑。

一天最多 8 站时 8! = 40320 种顺序，交通分钟数直接相加，很快；错误数只对比模型顺序更省时间的那些按从少到多去算，
找到第一个就停。超过 MAX_CHECKS 次还没找到就保留模型的顺序。

纯函数，不调用模型、不联网。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from itertools import permutations

from app.schemas.itinerary import DayOrder
from app.schemas.planning import OutlineDay, PlanOutline

MAX_STOPS = 8
MAX_CHECKS = 5000

# (from, to) -> 分钟数；没查到为 None
TravelMinutes = Mapping[tuple[str, str], int | None]
# 给一份完整的行程和一天的编号，返回这一天的错误数
DayErrors = Callable[[PlanOutline, int], int]


def path_minutes(order: tuple[str, ...] | list[str], travel: TravelMinutes) -> int | None:
    """按这个顺序走，相邻两站交通分钟数之和。有一段没查到返回 None。"""
    total = 0
    for a, b in zip(order, order[1:]):
        m = travel.get((a, b))
        if m is None:
            return None
        total += m
    return total


def _with_day(outline: PlanOutline, day: OutlineDay) -> PlanOutline:
    return outline.model_copy(update={"days": [day if d.dayNumber == day.dayNumber else d for d in outline.days]})


def _reorder(day: OutlineDay, order: tuple[str, ...]) -> OutlineDay:
    by_id = {s.poiId: s for s in day.stops}
    return day.model_copy(update={"stops": [by_id[p] for p in order]})


def optimize_day(
    outline: PlanOutline,
    day_number: int,
    *,
    known: set[str],
    travel: TravelMinutes,
    day_errors: DayErrors,
) -> tuple[OutlineDay, DayOrder]:
    """返回这一天（可能换了顺序）和说明。outline 是整份行程，算错误时其他天保持不变。"""
    day = next(d for d in outline.days if d.dayNumber == day_number)
    model_order = [s.poiId for s in day.stops]

    def kept(reason: str, minutes: int | None = None) -> tuple[OutlineDay, DayOrder]:
        return day, DayOrder(
            dayNumber=day_number, modelOrder=model_order, order=model_order,
            modelTransportMinutes=minutes, transportMinutes=minutes, changed=False, reason=reason,
        )

    if len(model_order) < 2:
        return kept("too-few-stops")
    if len(set(model_order)) != len(model_order) or any(p not in known for p in model_order):
        return kept("invalid-stops")
    if len(model_order) > MAX_STOPS:
        return kept("too-many-stops", path_minutes(model_order, travel))
    base = path_minutes(model_order, travel)
    if base is None:
        return kept("travel-unknown")

    # 比模型顺序更省时间的顺序，按交通分钟数从少到多（同样分钟数按字典序，结果稳定）
    better = sorted(
        (m, order)
        for order in permutations(model_order)
        if (m := path_minutes(order, travel)) is not None and m < base
    )
    if not better:
        return kept("already-shortest", base)

    limit = day_errors(outline, day_number)
    for checks, (minutes, order) in enumerate(better):
        if checks >= MAX_CHECKS:
            break
        candidate = _reorder(day, order)
        if day_errors(_with_day(outline, candidate), day_number) <= limit:
            return candidate, DayOrder(
                dayNumber=day_number, modelOrder=model_order, order=list(order),
                modelTransportMinutes=base, transportMinutes=minutes, changed=True, reason="shorter",
            )
    return kept("more-errors", base)


def optimize_outline(
    outline: PlanOutline,
    *,
    known: set[str],
    travel: TravelMinutes,
    day_errors: DayErrors,
) -> tuple[PlanOutline, list[DayOrder]]:
    """每一天依次优化。后面的天算错误时，前面的天已经换成新顺序。"""
    current = outline
    notes: list[DayOrder] = []
    for d in outline.days:
        new_day, note = optimize_day(current, d.dayNumber, known=known, travel=travel, day_errors=day_errors)
        current = _with_day(current, new_day)
        notes.append(note)
    return current, notes


def pairs_needed(outline: PlanOutline, known: set[str]) -> list[tuple[str, str]]:
    """每天里两两之间（两个方向）要查的交通。只算在候选里、不重复、不超过 MAX_STOPS 站的天。"""
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for day in outline.days:
        ids = [s.poiId for s in day.stops]
        if len(ids) < 2 or len(ids) > MAX_STOPS or len(set(ids)) != len(ids) or any(p not in known for p in ids):
            continue
        for a in ids:
            for b in ids:
                if a != b and (a, b) not in seen:
                    seen.add((a, b))
                    out.append((a, b))
    return out


def apply_order(outline: PlanOutline, notes: list[DayOrder] | None) -> PlanOutline:
    """把存下的重排结果套回模型的 outline（续聊时给模型看程序重排后的顺序）。对不上的天保持原样。"""
    if not notes:
        return outline
    by_day = {n.dayNumber: n for n in notes if n.changed}
    days = []
    for d in outline.days:
        n = by_day.get(d.dayNumber)
        if n is not None and sorted(n.order) == sorted(s.poiId for s in d.stops) and len(set(n.order)) == len(n.order):
            d = _reorder(d, tuple(n.order))
        days.append(d)
    return outline.model_copy(update={"days": days})
