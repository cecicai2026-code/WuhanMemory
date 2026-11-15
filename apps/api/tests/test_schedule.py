"""程序推钟点的测试（板块 6C）。纯函数，不调用模型、不联网；景点是虚构的测试景点。

测试景点的开放时间：周二到周日 09:00–17:00，最晚 16:00 入场，周一闭馆。2026-11-17 是周二，2026-11-16 是周一。
"""

from __future__ import annotations

from typing import Any

from app.schemas.planning import PlanOutline, TripFrame
from app.schemas.route import RouteError
from app.services.planning.schedule import schedule
from app.services.planning.validate import validate_itinerary
from tests.poi_factory import clean_poi, hours
from tests.test_validate_itinerary import library, route

TUESDAY = TripFrame(days=1, startDate="2026-11-17", pace="moderate")


def outline(*days: tuple[str, list[tuple[str, int]]]) -> PlanOutline:
    return PlanOutline.model_validate({
        "title": "测试",
        "days": [
            {"dayNumber": n, "start": start, "stops": [{"poiId": p, "stayMinutes": m, "reason": "测试"} for p, m in stops]}
            for n, (start, stops) in enumerate(days, start=1)
        ],
    })


def times(draft: Any, day: int = 0) -> list[tuple[str, str, str]]:
    return [(s.poiId, s.arrive, s.leave) for s in draft.days[day].stops]


POIS = library(clean_poi("a"), clean_poi("b"), clean_poi("c"))


def test_arrive_is_previous_leave_plus_real_travel_plus_slack() -> None:
    legs = {("a", "b"): route(28), ("b", "c"): route(9, mode="walk")}
    draft, issues = schedule(outline(("09:30", [("a", 120), ("b", 90), ("c", 60)])), pois=POIS, legs=legs, frame=TUESDAY)
    # 11:30 离开 a，公交 28 分钟 + 10 分钟 → 12:08，取整到 12:10；b 待 90 分钟到 13:40；走 9 + 10 → 13:59 → 14:00
    assert times(draft) == [("a", "09:30", "11:30"), ("b", "12:10", "13:40"), ("c", "14:00", "15:00")]
    assert issues == []
    # 推出来的行程交给校验：交通时间不够、时间重叠都不会出现
    report = validate_itinerary(draft, pois=POIS, legs=legs, frame=TUESDAY, today=TUESDAY.startDate)  # type: ignore[arg-type]
    assert not {"transport-too-short", "overlap", "transport-tight"} & {i.code for i in report.issues}


def test_rounding_only_goes_later() -> None:
    legs = {("a", "b"): route(20)}
    draft, _ = schedule(outline(("09:03", [("a", 60), ("b", 60)])), pois=POIS, legs=legs, frame=TUESDAY)
    # 出发 09:03 → 09:05；10:05 离开，+20+10 = 10:35，正好整 5 分钟不动
    assert times(draft) == [("a", "09:05", "10:05"), ("b", "10:35", "11:35")]


def test_waits_until_opening() -> None:
    draft, _ = schedule(outline(("08:00", [("a", 60)])), pois=POIS, legs={}, frame=TUESDAY)
    assert times(draft) == [("a", "09:00", "10:00")]


def test_waits_for_the_afternoon_period() -> None:
    lunch_break = clean_poi("a")
    lunch_break["openingHours"] = hours({
        "allDay": False,
        "periods": [
            {"weekdays": [1, 2, 3, 4, 5, 6, 7], "open": "09:00", "close": "12:00", "lastEntry": "11:30"},
            {"weekdays": [1, 2, 3, 4, 5, 6, 7], "open": "14:00", "close": "17:00", "lastEntry": "16:30"},
        ],
        "closedWeekdays": [],
    })
    pois = library(lunch_break, clean_poi("b"))
    draft, _ = schedule(outline(("12:30", [("a", 60)])), pois=pois, legs={}, frame=TUESDAY)
    # 12:30 上午时段已经关了，等到下午 14:00
    assert times(draft) == [("a", "14:00", "15:00")]


def test_no_wait_when_hours_unknown_or_closed_day() -> None:
    unknown = clean_poi("a")
    unknown["openingHours"] = hours(None)
    draft, _ = schedule(outline(("08:00", [("a", 60)])), pois=library(unknown), legs={}, frame=TUESDAY)
    assert times(draft) == [("a", "08:00", "09:00")]
    monday = TripFrame(days=1, startDate="2026-11-16", pace="moderate")
    draft, _ = schedule(outline(("08:00", [("a", 60)])), pois=POIS, legs={}, frame=monday)
    assert times(draft) == [("a", "08:00", "09:00")]  # 闭馆日不等，交给校验报"闭馆"
    report = validate_itinerary(draft, pois=POIS, legs={}, frame=monday, today=monday.startDate)  # type: ignore[arg-type]
    assert "closed-day" in {i.code for i in report.errors}


def test_long_stay_still_breaks_closing_time() -> None:
    # 程序只管钟点怎么推，停留太久照样由校验报"关门后才离开"，交给模型修正
    draft, _ = schedule(outline(("15:00", [("a", 180)])), pois=POIS, legs={}, frame=TUESDAY)
    report = validate_itinerary(draft, pois=POIS, legs={}, frame=TUESDAY, today=TUESDAY.startDate)  # type: ignore[arg-type]
    assert "after-close" in {i.code for i in report.errors}


def test_unknown_transport_stops_the_day() -> None:
    bad = route(None, status="error")
    bad = bad.model_copy(update={"error": RouteError(code="amap-test", message="测试：查询出错")})
    draft, issues = schedule(outline(("09:30", [("a", 60), ("b", 60), ("c", 60)])), pois=POIS,
                             legs={("a", "b"): bad, ("b", "c"): route(10)}, frame=TUESDAY)
    assert [i.code for i in issues] == ["transport-unknown"]
    assert "测试：查询出错" in issues[0].message
    assert times(draft)[1:] == [("b", "", ""), ("c", "", "")]
    assert [st.scheduled for st in draft.days[0].stops] == [True, False, False]


def test_past_midnight_is_an_error() -> None:
    draft, issues = schedule(outline(("20:00", [("a", 200), ("b", 120)])), pois=POIS,
                             legs={("a", "b"): route(10)}, frame=TUESDAY)
    assert [i.code for i in issues] == ["day-overflow"]
    assert times(draft)[1] == ("b", "", "")
    # 推不出钟点的站不再被校验报成别的错（以前的占位钟点会被报"离开不晚于到达""晚于 22:00"）
    report = validate_itinerary(draft, pois=POIS, legs={("a", "b"): route(10)}, frame=TUESDAY, today=TUESDAY.startDate)  # type: ignore[arg-type]
    errors = [i.code for i in report.errors]
    assert "time-order" not in errors and "bad-time" not in errors
    # a 20:00 到、23:20 走：晚于 17:00 关门和 22:00 是真的错，照样报
    assert "after-close" in errors and "day-window" in errors


def test_bad_start_time() -> None:
    draft, issues = schedule(outline(("9点", [("a", 60)])), pois=POIS, legs={}, frame=TUESDAY)
    assert [i.code for i in issues] == ["bad-time"]


def test_unknown_poi_gets_slack_only_and_is_left_to_validation() -> None:
    draft, issues = schedule(outline(("09:30", [("a", 60), ("made-up", 60)])), pois=POIS, legs={}, frame=TUESDAY)
    assert issues == []
    assert times(draft)[1] == ("made-up", "10:40", "11:40")
    report = validate_itinerary(draft, pois=POIS, legs={}, frame=TUESDAY, today=TUESDAY.startDate)  # type: ignore[arg-type]
    assert "unknown-poi" in {i.code for i in report.errors}


def test_date_undecided_uses_hours_only_if_every_day_is_the_same() -> None:
    undecided = TripFrame(days=1, startDate=None, pace="moderate")
    draft, _ = schedule(outline(("08:00", [("a", 60)])), pois=POIS, legs={}, frame=undecided)
    assert times(draft) == [("a", "09:00", "10:00")]
