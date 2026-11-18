"""每天站点顺序由程序按真实交通时间重排（ADR 0010）的测试。纯函数，不联网、不调用模型。"""

from __future__ import annotations

from app.schemas.planning import OutlineDay, OutlineStop, PlanOutline
from app.services.planning.order import (
    MAX_STOPS,
    apply_order,
    optimize_day,
    optimize_outline,
    pairs_needed,
    path_minutes,
)


def outline(*days: list[str]) -> PlanOutline:
    return PlanOutline(
        title="测试",
        days=[
            OutlineDay(dayNumber=i, start="09:00", stops=[OutlineStop(poiId=p, stayMinutes=60) for p in ids])
            for i, ids in enumerate(days, start=1)
        ],
    )


def line(positions: dict[str, int]) -> dict[tuple[str, str], int | None]:
    """站点排在一条直线上，两站之间的分钟数 = 位置差 × 10。"""
    return {(a, b): abs(pa - pb) * 10 for a, pa in positions.items() for b, pb in positions.items() if a != b}


def no_errors(_o: PlanOutline, _d: int) -> int:
    return 0


KNOWN = {"a", "b", "c", "d", "e", "f", "g", "h", "i"}


def test_finds_the_shortest_open_path() -> None:
    travel = line({"a": 0, "b": 1, "c": 2, "d": 3})
    o = outline(["a", "c", "b", "d"])  # 20 + 10 + 20 = 50
    day, note = optimize_day(o, 1, known=KNOWN, travel=travel, day_errors=no_errors)
    assert [s.poiId for s in day.stops] in (["a", "b", "c", "d"], ["d", "c", "b", "a"])
    assert note.changed and note.reason == "shorter"
    assert note.modelTransportMinutes == 50 and note.transportMinutes == 30
    assert note.modelOrder == ["a", "c", "b", "d"]


def test_first_stop_is_not_fixed() -> None:
    travel = line({"a": 0, "b": 1, "c": 2})
    o = outline(["b", "a", "c"])  # 10 + 20 = 30；从 a 或 c 出发是 20
    day, note = optimize_day(o, 1, known=KNOWN, travel=travel, day_errors=no_errors)
    assert [s.poiId for s in day.stops][0] != "b"
    assert note.transportMinutes == 20


def test_stays_and_reasons_move_with_their_stop() -> None:
    travel = line({"a": 0, "b": 1, "c": 2})
    o = PlanOutline(days=[OutlineDay(dayNumber=1, start="09:00", stops=[
        OutlineStop(poiId="a", stayMinutes=30, reason="甲"),
        OutlineStop(poiId="c", stayMinutes=90, reason="丙"),
        OutlineStop(poiId="b", stayMinutes=60, reason="乙"),
    ])])
    day, _ = optimize_day(o, 1, known=KNOWN, travel=travel, day_errors=no_errors)
    assert {(s.poiId, s.stayMinutes, s.reason) for s in day.stops} == {("a", 30, "甲"), ("b", 60, "乙"), ("c", 90, "丙")}
    assert day.start == "09:00"


def test_keeps_the_model_order_when_it_is_already_shortest() -> None:
    travel = line({"a": 0, "b": 1, "c": 2})
    day, note = optimize_day(outline(["a", "b", "c"]), 1, known=KNOWN, travel=travel, day_errors=no_errors)
    assert [s.poiId for s in day.stops] == ["a", "b", "c"]
    assert not note.changed and note.reason == "already-shortest"
    assert note.modelTransportMinutes == note.transportMinutes == 20


def test_never_takes_an_order_with_more_errors() -> None:
    travel = line({"a": 0, "b": 1, "c": 2})

    def errors(o: PlanOutline, d: int) -> int:
        # 只要 b 不在第一站就多一个错误（例如 b 下午关门）
        return 0 if o.days[0].stops[0].poiId == "b" else 1

    day, note = optimize_day(outline(["b", "a", "c"]), 1, known=KNOWN, travel=travel, day_errors=errors)
    assert [s.poiId for s in day.stops] == ["b", "a", "c"]
    assert not note.changed and note.reason == "more-errors"


def test_takes_the_shortest_order_that_does_not_add_errors() -> None:
    travel = line({"a": 0, "b": 1, "c": 2, "d": 3})

    def errors(o: PlanOutline, d: int) -> int:
        order = [s.poiId for s in o.days[0].stops]
        return 1 if order in (["a", "b", "c", "d"], ["d", "c", "b", "a"]) else 0  # 最短的两个都不行

    day, note = optimize_day(outline(["a", "d", "b", "c"]), 1, known=KNOWN, travel=travel, day_errors=errors)
    order = [s.poiId for s in day.stops]
    assert note.changed and order not in (["a", "b", "c", "d"], ["d", "c", "b", "a"])
    assert note.transportMinutes == path_minutes(order, travel) == 40
    assert note.modelTransportMinutes == 60  # a→d 30 + d→b 20 + b→c 10


def test_fewer_errors_is_fine() -> None:
    travel = line({"a": 0, "b": 1, "c": 2})

    def errors(o: PlanOutline, d: int) -> int:
        return 2 if [s.poiId for s in o.days[0].stops] == ["a", "c", "b"] else 0

    _, note = optimize_day(outline(["a", "c", "b"]), 1, known=KNOWN, travel=travel, day_errors=errors)
    assert note.changed


def test_equal_time_keeps_the_model_order() -> None:
    travel = {(x, y): 10 for x in "abc" for y in "abc" if x != y}
    day, note = optimize_day(outline(["c", "a", "b"]), 1, known=KNOWN, travel=travel, day_errors=no_errors)
    assert [s.poiId for s in day.stops] == ["c", "a", "b"]
    assert note.reason == "already-shortest"


def test_orders_with_unknown_legs_are_skipped() -> None:
    travel = line({"a": 0, "b": 1, "c": 2})
    travel[("a", "b")] = None
    travel[("b", "a")] = None
    travel[("b", "c")] = None
    travel[("c", "b")] = None
    _, note = optimize_day(outline(["a", "c", "b"]), 1, known=KNOWN, travel=travel, day_errors=no_errors)
    assert note.reason == "travel-unknown" and not note.changed


def test_days_that_are_not_reordered() -> None:
    travel = line({p: i for i, p in enumerate("abcdefghi")})
    assert optimize_day(outline(["a"]), 1, known=KNOWN, travel=travel, day_errors=no_errors)[1].reason == "too-few-stops"
    assert optimize_day(outline(["a", "x"]), 1, known=KNOWN, travel=travel, day_errors=no_errors)[1].reason == "invalid-stops"
    assert optimize_day(outline(["a", "b", "a"]), 1, known=KNOWN, travel=travel, day_errors=no_errors)[1].reason == "invalid-stops"
    many = list("abcdefghi")[: MAX_STOPS + 1]
    assert optimize_day(outline(many), 1, known=KNOWN, travel=travel, day_errors=no_errors)[1].reason == "too-many-stops"


def test_each_day_is_reordered_on_its_own() -> None:
    travel = line({"a": 0, "b": 1, "c": 2, "d": 10, "e": 11, "f": 12})
    new, notes = optimize_outline(outline(["a", "c", "b"], ["d", "e", "f"]), known=KNOWN, travel=travel, day_errors=no_errors)
    assert sorted(s.poiId for s in new.days[0].stops) == ["a", "b", "c"]
    assert [s.poiId for s in new.days[1].stops] == ["d", "e", "f"]
    assert [n.changed for n in notes] == [True, False]


def test_pairs_needed_covers_both_directions_within_a_day() -> None:
    pairs = pairs_needed(outline(["a", "b"], ["c", "x"]), KNOWN)
    assert sorted(pairs) == [("a", "b"), ("b", "a")]


def test_apply_order_restores_the_program_order() -> None:
    travel = line({"a": 0, "b": 1, "c": 2})
    model = outline(["a", "c", "b"])
    new, notes = optimize_outline(model, known=KNOWN, travel=travel, day_errors=no_errors)
    assert apply_order(model, notes) == new
    assert apply_order(model, None) == model


def test_order_eval_rebuilds_the_model_order_from_an_old_draft() -> None:
    from app.schemas.planning import PlanDay, PlanDraft, PlanStop
    from app.tools.order_eval import _from_draft

    draft = PlanDraft(title="旧", days=[PlanDay(dayNumber=1, stops=[
        PlanStop(poiId="a", arrive="09:30", leave="11:00"),
        PlanStop(poiId="b", arrive="11:30", leave="12:00"),
    ])])
    o = _from_draft(draft)
    assert o is not None and o.days[0].start == "09:30"
    assert [(s.poiId, s.stayMinutes) for s in o.days[0].stops] == [("a", 90), ("b", 30)]
    bad = PlanDraft(days=[PlanDay(dayNumber=1, stops=[PlanStop(poiId="a", arrive="", leave="")])])
    assert _from_draft(bad) is None
