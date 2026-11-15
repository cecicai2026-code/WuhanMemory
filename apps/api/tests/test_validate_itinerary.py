"""validate_itinerary 的单元测试。

景点资料全部是虚构的测试数据（来自 tests/poi_factory.py，"测试景点"、example.com），
路线是手写的假结果，不调用模型，也不联网。2026-11-16 是周一，2026-11-17 是周二。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.schemas.planning import PlanDraft, TripFrame, ValidationReport
from app.schemas.poi import PoiFile
from app.schemas.route import RouteOut
from app.services.planning.validate import validate_itinerary
from tests.poi_factory import clean_poi, good_poi, hours

TODAY = date(2026, 11, 15)
MONDAY = date(2026, 11, 16)
TUESDAY = date(2026, 11, 17)


def library(*pois: dict[str, Any]) -> dict[str, PoiFile]:
    return {p["id"]: PoiFile.model_validate(p) for p in pois}


def route(minutes: int | None, mode: str = "transit", status: str = "ok", cache: str = "cached") -> RouteOut:
    return RouteOut(mode=mode, status=status, durationMinutes=minutes, cache=cache)  # type: ignore[arg-type]


def draft(*days: list[tuple[str, str, str]]) -> PlanDraft:
    return PlanDraft.model_validate(
        {
            "days": [
                {"dayNumber": i, "stops": [{"poiId": p, "arrive": a, "leave": l} for p, a, l in stops]}
                for i, stops in enumerate(days, start=1)
            ]
        }
    )


def run(
    plan: PlanDraft,
    pois: dict[str, PoiFile],
    legs: dict[tuple[str, str], RouteOut | None] | None = None,
    *,
    start: date | None = TUESDAY,
    pace: str = "moderate",
    today: date = TODAY,
) -> ValidationReport:
    frame = TripFrame(days=len(plan.days), startDate=start, pace=pace)  # type: ignore[arg-type]
    return validate_itinerary(plan, pois=pois, legs=legs or {}, frame=frame, today=today)


def codes(report: ValidationReport, level: str | None = None) -> list[str]:
    return [i.code for i in report.issues if level is None or i.level == level]


# ---------- 通过 ----------


def test_clean_itinerary_passes() -> None:
    pois = library(clean_poi("a"), clean_poi("b"))
    plan = draft([("a", "09:30", "11:30"), ("b", "12:30", "15:00")])
    report = run(plan, pois, {("a", "b"): route(40)})
    assert report.status == "passed", report.issues
    assert report.issues == []


# ---------- 你点名的 7 种情况 ----------


def test_closed_day_is_error() -> None:
    pois = library(clean_poi("a"))
    report = run(draft([("a", "10:00", "12:00")]), pois, start=MONDAY)
    assert report.status == "failed"
    [issue] = report.errors
    assert issue.code == "closed-day" and issue.poiId == "a" and issue.fields == ["openingHours"]
    assert "周一" in issue.message and "2026-11-16" in issue.message


def test_arrive_after_last_entry_is_error() -> None:
    pois = library(clean_poi("a"))
    report = run(draft([("a", "16:20", "16:50")]), pois)
    assert "after-last-entry" in codes(report, "error")
    assert report.status == "failed"


def test_arrive_after_close_without_last_entry_is_error() -> None:
    poi = clean_poi("a", openingHours=hours({"periods": [{"open": "09:00", "close": "17:00"}]}))
    report = run(draft([("a", "17:00", "17:30")]), library(poi))
    assert "after-last-entry" in codes(report, "error")


def test_before_open_and_after_close_are_errors() -> None:
    pois = library(clean_poi("a"))
    report = run(draft([("a", "08:30", "17:30")]), pois)
    assert {"before-open", "after-close"} <= set(codes(report, "error"))


def test_overlapping_stops_are_error() -> None:
    pois = library(clean_poi("a"), clean_poi("b"))
    plan = draft([("a", "09:30", "12:00"), ("b", "11:30", "14:00")])
    report = run(plan, pois, {("a", "b"): route(20)})
    assert codes(report, "error") == ["overlap"]
    # 重叠了就不再报交通时间不够，免得同一个问题报两遍
    assert "transport-too-short" not in codes(report)


def test_not_enough_transport_time_is_error() -> None:
    pois = library(clean_poi("a"), clean_poi("b"))
    plan = draft([("a", "09:30", "11:30"), ("b", "11:50", "14:00")])
    report = run(plan, pois, {("a", "b"): route(45)})
    assert codes(report, "error") == ["transport-too-short"]
    assert "45 分钟" in report.errors[0].message and "20 分钟" in report.errors[0].message


def test_unknown_poi_is_error() -> None:
    pois = library(clean_poi("a"))
    report = run(draft([("a", "09:30", "11:30"), ("made-up-place", "12:30", "14:00")]), pois)
    assert "unknown-poi" in codes(report, "error")
    assert report.status == "failed"


def test_expired_data_is_warning_naming_the_fact() -> None:
    # 开放时间 2027-02-08 过期；按 2027-03-01 校验
    pois = library(clean_poi("a"))
    report = run(draft([("a", "09:30", "11:30")]), pois, start=date(2027, 3, 2), today=date(2027, 3, 1))
    assert report.status == "warning"
    expired = [i for i in report.issues if i.code == "data-expired"]
    assert expired and expired[0].fields == ["openingHours"]
    assert "开放时间" in expired[0].message and "2027-02-08" in expired[0].message


def test_missing_opening_hours_is_warning_not_pass() -> None:
    poi = clean_poi("a", openingHours=hours(None))
    report = run(draft([("a", "09:30", "11:30")]), library(poi))
    assert report.status == "warning"
    [issue] = report.warnings
    assert issue.code == "hours-unknown" and "开放时间未知，无法校验" in issue.message


# ---------- 其余开放时间规则 ----------


def test_month_not_covered_is_unknown_not_closed() -> None:
    # 资料只写了 4 到 12 月，1 月没写：不算闭馆，算"无法校验"
    poi = clean_poi("a", openingHours=hours({"periods": [{"months": [4, 5, 6, 7, 8, 9, 10, 11, 12], "open": "09:00", "close": "17:00"}]}))
    report = run(draft([("a", "09:30", "11:30")]), library(poi), start=date(2027, 1, 12))
    assert report.status == "warning"
    assert codes(report) == ["hours-unknown"]
    assert "1 月" in report.issues[0].message


def test_all_day_open_skips_time_check() -> None:
    poi = clean_poi("a", openingHours=hours({"allDay": True}))
    report = run(draft([("a", "08:00", "10:00")]), library(poi))
    assert report.status == "passed"


def test_any_matching_period_is_enough() -> None:
    poi = clean_poi(
        "a",
        openingHours=hours({"periods": [{"open": "08:00", "close": "11:00"}, {"open": "14:00", "close": "18:00"}]}),
    )
    assert run(draft([("a", "14:30", "16:30")]), library(poi)).status == "passed"
    assert "before-open" in codes(run(draft([("a", "12:00", "13:30")]), library(poi)))


def test_unknown_date_warns_and_still_checks_uniform_hours() -> None:
    pois = library(clean_poi("a"))
    report = run(draft([("a", "16:30", "17:00")]), pois, start=None)
    assert "date-unknown" in codes(report, "warning")
    assert "closed-day-unchecked" in codes(report, "warning")
    # 每天时段都一样，照样能查出过了最晚入场
    assert "after-last-entry" in codes(report, "error")


def test_closed_day_note_is_shown() -> None:
    poi = clean_poi("a")
    poi["openingHours"]["value"]["note"] = "周一闭馆，国家法定节假日除外。"
    report = run(draft([("a", "10:00", "12:00")]), library(poi), start=MONDAY)
    assert "法定节假日除外" in report.errors[0].message


# ---------- 交通 ----------


def test_tight_transport_is_warning() -> None:
    pois = library(clean_poi("a"), clean_poi("b"))
    plan = draft([("a", "09:30", "11:30"), ("b", "12:15", "14:30")])
    report = run(plan, pois, {("a", "b"): route(40)})
    assert report.status == "warning" and codes(report) == ["transport-tight"]


def test_route_not_found_is_warning() -> None:
    pois = library(clean_poi("a"), clean_poi("b"))
    plan = draft([("a", "09:30", "11:30"), ("b", "12:30", "14:30")])
    for legs in ({}, {("a", "b"): None}, {("a", "b"): route(None, status="error")}):
        report = run(plan, pois, legs)
        assert report.status == "warning" and codes(report) == ["route-unknown"]


def test_stale_route_is_warning() -> None:
    pois = library(clean_poi("a"), clean_poi("b"))
    plan = draft([("a", "09:30", "11:30"), ("b", "12:30", "14:30")])
    report = run(plan, pois, {("a", "b"): route(30, cache="stale")})
    assert codes(report) == ["route-stale"]


def test_route_lookup_uses_direction() -> None:
    # 只查到了 b→a，没有 a→b，不能拿反方向的时间用
    pois = library(clean_poi("a"), clean_poi("b"))
    plan = draft([("a", "09:30", "11:30"), ("b", "12:30", "14:30")])
    assert codes(run(plan, pois, {("b", "a"): route(10)})) == ["route-unknown"]


# ---------- 每天的总时长 ----------


def test_day_too_long_depends_on_pace() -> None:
    allday = hours({"allDay": True})
    pois = library(*(clean_poi(x, openingHours=allday) for x in "abc"))
    legs = {("a", "b"): route(20), ("b", "c"): route(20)}
    # 09:00 到 18:30 共 9.5 小时
    plan = draft([("a", "09:00", "12:00"), ("b", "12:30", "15:30"), ("c", "16:00", "18:30")])
    assert "day-too-long" in codes(run(plan, pois, legs, pace="relaxed"), "error")
    assert run(plan, pois, legs, pace="moderate").status == "passed"


def test_day_window() -> None:
    allday = hours({"allDay": True})
    pois = library(clean_poi("a", openingHours=allday), clean_poi("b", openingHours=allday))
    assert codes(run(draft([("a", "07:30", "09:30")]), pois), "error") == ["day-window"]
    assert codes(run(draft([("b", "20:30", "22:30")]), pois), "error") == ["day-window"]


# ---------- 结构 ----------


def test_wrong_day_count() -> None:
    pois = library(clean_poi("a"))
    plan = draft([("a", "09:30", "11:30")])
    frame = TripFrame(days=2, startDate=TUESDAY)
    report = validate_itinerary(plan, pois=pois, legs={}, frame=frame, today=TODAY)
    assert "day-count" in codes(report, "error")


def test_day_numbers_must_be_in_order() -> None:
    pois = library(clean_poi("a"), clean_poi("b"))
    plan = draft([("a", "09:30", "11:30")], [("b", "09:30", "11:30")])
    plan.days[1].dayNumber = 3
    assert "day-number" in codes(run(plan, pois), "error")


def test_duplicate_poi_is_error() -> None:
    pois = library(clean_poi("a"))
    plan = draft([("a", "09:30", "11:30")], [("a", "09:30", "11:30")])
    report = run(plan, pois)
    assert codes(report, "error") == ["duplicate-poi"]


def test_empty_day_is_error() -> None:
    pois = library(clean_poi("a"))
    report = run(draft([("a", "09:30", "11:30")], []), pois)
    assert "empty-day" in codes(report, "error")


def test_bad_time_format_and_order() -> None:
    pois = library(clean_poi("a"), clean_poi("b"))
    assert "bad-time" in codes(run(draft([("a", "9点半", "11:30")]), pois))
    assert "bad-time" in codes(run(draft([("a", "25:00", "26:00")]), pois))
    assert "time-order" in codes(run(draft([("b", "11:30", "11:30")]), pois))


# ---------- 停留时间 ----------


def test_short_stay_is_warning() -> None:
    pois = library(clean_poi("a"))
    report = run(draft([("a", "09:30", "10:20")]), pois)  # 50 分钟，建议 120
    assert codes(report) == ["stay-short"]


def test_unknown_duration_is_warning() -> None:
    poi = clean_poi("a")
    poi["recommendedDurationMinutes"] = {"value": None, "verification": "todo", "todo": "TODO(Cecilia): 测试"}
    report = run(draft([("a", "09:30", "11:30")]), library(poi))
    assert codes(report) == ["duration-unknown"]


# ---------- 待确认、待补充的资料 ----------


def test_placeholder_and_missing_data_listed_per_poi() -> None:
    poi = good_poi("p")  # 开放时间、预约是占位，支付方式是 TODO
    report = run(draft([("p", "09:30", "11:30")]), library(poi))
    assert report.status == "warning"
    pending = [i for i in report.issues if i.code == "data-pending"]
    missing = [i for i in report.issues if i.code == "data-missing"]
    assert len(pending) == 1 and set(pending[0].fields) == {"openingHours", "reservation"}
    assert "待确认" in pending[0].message
    assert len(missing) == 1 and missing[0].fields == ["payment"]


def test_every_issue_names_its_place() -> None:
    poi = good_poi("p")
    poi["name"] = "某测试馆"
    report = run(draft([("p", "16:30", "17:30")]), library(poi), start=MONDAY)
    for issue in report.issues:
        if issue.poiId:
            assert "某测试馆" in issue.message


# ---------- 暂停开放（2026-11-15 加） ----------


def closed(poi: dict[str, Any]) -> dict[str, Any]:
    poi["operatingStatus"] = {
        "value": {"code": "closed-temporarily", "note": "测试：修缮"},
        "verification": "confirmed",
        "sourceId": "official",
        "lastCheckedAt": "2026-11-10",
        "expiresAt": "2026-12-14",
    }
    return poi


def test_closed_poi_is_an_error() -> None:
    pois = library(closed(clean_poi("a")))
    report = run(draft([("a", "09:30", "11:30")]), pois)
    assert "poi-closed" in codes(report, "error")


def test_closed_poi_is_not_a_candidate() -> None:
    from app.schemas.planning import TravelerPreferences
    from app.services.planning.candidates import select_candidates

    a, b = closed(clean_poi("a")), clean_poi("b")
    a["name"], b["name"] = "关着的寺", "开着的楼"
    lib = [PoiFile.model_validate(a), PoiFile.model_validate(b)]

    c = select_candidates(lib, TravelerPreferences(mustVisit=["关着的寺", "不存在的塔"]))
    assert list(c.pois) == ["b"]
    assert c.closed_requested == ["关着的寺"]
    assert c.not_in_library == ["不存在的塔"]
