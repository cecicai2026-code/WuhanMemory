"""三种侧重（经典必去、轻松少走路、深度文化）的候选、节奏和额外校验规则的测试（板块 5B）。

全部是虚构的测试景点（"测试景点x"）；标签用真实资料里出现的写法（"5A"、"历史"等），因为规则按标签判断。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.schemas.planning import PlanDraft, TravelerPreferences, TripFrame, ValidationIssue, ValidationReport
from app.schemas.poi import PoiFile
from app.schemas.route import RouteOut
from app.services.planning.candidates import select_candidates
from app.services.planning.emphasis import (
    EMPHASES,
    candidates_for,
    check_emphasis,
    emphasis_frame,
    merge_issues,
    walk_limit,
)
from tests.poi_factory import clean_poi

TODAY = date(2026, 11, 15)


def p(poi_id: str, tags: list[str], **changes: Any) -> PoiFile:
    return PoiFile.model_validate(clean_poi(poi_id, tags=tags, **changes))


LIBRARY = [
    p("tower", ["历史", "5A"]),
    p("museum", ["文物", "5A"]),
    p("lake", ["湖景", "5A"]),
    p("street", ["老街", "拍照"]),
    p("snack", ["小吃"]),
]


def cands(emphasis: str, **prefs: Any):
    base = select_candidates(LIBRARY, TravelerPreferences(days=1, **prefs))
    return candidates_for(EMPHASES[emphasis], base, LIBRARY)


def draft(*days: list[tuple[str, str, str]]) -> PlanDraft:
    return PlanDraft.model_validate(
        {"days": [{"dayNumber": n, "stops": [{"poiId": i, "arrive": a, "leave": b} for i, a, b in s]} for n, s in enumerate(days, 1)]}
    )


def walk(minutes: int, meters: int | None) -> RouteOut:
    return RouteOut(mode="walk", status="ok", durationMinutes=minutes, distanceMeters=meters, walkingDistanceMeters=meters)


def transit(minutes: int, walking: int | None) -> RouteOut:
    return RouteOut(mode="transit", status="ok", durationMinutes=minutes, distanceMeters=5000, walkingDistanceMeters=walking)


FRAME = TripFrame(days=1, startDate=date(2026, 11, 17), pace="moderate")


def check(emphasis: str, d: PlanDraft, legs: dict[tuple[str, str], RouteOut] | None = None, **prefs: Any) -> list[ValidationIssue]:
    c = cands(emphasis, **prefs)
    return check_emphasis(EMPHASES[emphasis], d, candidates=c, legs=legs or {}, frame=emphasis_frame(EMPHASES[emphasis], FRAME))


def codes(issues: list[ValidationIssue]) -> list[str]:
    return [i.code for i in issues]


# ---------- 候选 ----------


def test_order_is_classic_relaxed_culture() -> None:
    assert list(EMPHASES) == ["classic", "relaxed", "culture"]
    assert [e.label for e in EMPHASES.values()] == ["经典必去", "轻松少走路", "深度文化"]


def test_classic_keeps_everything_and_makes_5a_must_visit() -> None:
    c = cands("classic")
    assert set(c.pois) == {"tower", "museum", "lake", "street", "snack"}
    assert c.must_visit == ["tower", "museum", "lake"]
    # 5A 排在前面
    assert list(c.pois)[:3] == ["tower", "museum", "lake"]


def test_classic_respects_avoid_and_user_must_visit_first() -> None:
    """用户点名了必去时，以用户点名的为准：5A 不再标成必去，只排在前面（2026-11-15 Cecilia 定，评测 r07）。"""
    c = cands("classic", avoid=["测试景点lake"], mustVisit=["测试景点snack"])
    assert "lake" not in c.pois
    assert c.must_visit == ["snack"]
    assert list(c.pois)[:3] == ["snack", "tower", "museum"]


def test_classic_user_named_5a_stays_must_visit() -> None:
    c = cands("classic", mustVisit=["测试景点museum"])
    assert c.must_visit == ["museum"]


def test_relaxed_uses_the_same_candidates() -> None:
    assert set(cands("relaxed").pois) == {"tower", "museum", "lake", "street", "snack"}
    assert cands("relaxed").must_visit == []


def test_culture_keeps_only_culture_tags_plus_user_must_visit() -> None:
    assert set(cands("culture").pois) == {"tower", "museum", "street"}
    c = cands("culture", mustVisit=["测试景点snack"])
    assert set(c.pois) == {"tower", "museum", "street", "snack"}
    assert c.must_visit == ["snack"]


def test_closed_poi_never_a_candidate() -> None:
    closed = p(
        "temple",
        ["历史"],
        operatingStatus={"value": {"code": "closed-temporarily"}, "verification": "confirmed", "sourceId": "official",
                         "lastCheckedAt": "2026-11-10", "expiresAt": "2026-12-14"},
    )
    base = select_candidates([*LIBRARY, closed], TravelerPreferences(days=1))
    for e in EMPHASES.values():
        assert "temple" not in candidates_for(e, base, [*LIBRARY, closed]).pois


# ---------- 节奏和交通 ----------


def test_relaxed_forces_relaxed_pace() -> None:
    assert emphasis_frame(EMPHASES["relaxed"], FRAME).pace == "relaxed"
    assert emphasis_frame(EMPHASES["classic"], FRAME).pace == "moderate"
    assert emphasis_frame(EMPHASES["culture"], FRAME.model_copy(update={"pace": "intensive"})).pace == "intensive"


def test_relaxed_walks_at_most_ten_minutes() -> None:
    assert walk_limit(EMPHASES["relaxed"]) == 10
    assert walk_limit(EMPHASES["classic"]) is None


# ---------- 经典必去 ----------


def test_classic_missing_5a_is_an_error() -> None:
    issues = check("classic", draft([("tower", "09:00", "11:00"), ("museum", "12:00", "15:00")]))
    assert codes(issues) == ["emphasis-must-5a"]
    assert issues[0].level == "error" and "测试景点lake" in issues[0].message and issues[0].poiId == "lake"


def test_classic_with_all_5a_passes() -> None:
    d = draft([("tower", "09:00", "10:30"), ("museum", "11:00", "13:00"), ("lake", "14:00", "16:00")])
    assert check("classic", d) == []


def test_classic_with_user_must_visit_skipped_5a_is_a_warning() -> None:
    """用户点名了必去：没排的 5A 是警告，不是错误（r07：一天、必去武大，加上 5A 一天可能排不下）。"""
    d = draft([("snack", "09:00", "11:00"), ("tower", "12:00", "15:00")])
    issues = check("classic", d, mustVisit=["测试景点snack"])
    assert codes(issues) == ["emphasis-5a-skipped", "emphasis-5a-skipped"]
    assert all(i.level == "warning" for i in issues)
    assert {i.poiId for i in issues} == {"museum", "lake"}
    assert "你点名了必去的景点" in issues[0].message


def test_classic_user_named_5a_missing_is_still_an_error() -> None:
    d = draft([("snack", "09:00", "11:00")])
    issues = check("classic", d, mustVisit=["测试景点museum"])
    errors = [i for i in issues if i.level == "error"]
    assert codes(errors) == ["emphasis-must-5a"] and errors[0].poiId == "museum"
    assert sorted(i.poiId for i in issues if i.level == "warning") == ["lake", "tower"]


def test_classic_does_not_require_avoided_5a() -> None:
    d = draft([("tower", "09:00", "11:00"), ("museum", "12:00", "15:00")])
    assert check("classic", d, avoid=["测试景点lake"]) == []


# ---------- 轻松少走路 ----------


def test_relaxed_too_many_stops() -> None:
    d = draft([("tower", "09:00", "10:00"), ("museum", "10:30", "11:30"), ("lake", "12:00", "13:00"), ("street", "13:30", "14:30")])
    legs = {("tower", "museum"): walk(5, 300), ("museum", "lake"): walk(5, 300), ("lake", "street"): walk(5, 300)}
    issues = check("relaxed", d, legs)
    assert codes(issues) == ["emphasis-too-many-stops"]
    assert issues[0].dayNumber == 1 and "4 站" in issues[0].message


def test_relaxed_must_end_by_half_past_five() -> None:
    assert check("relaxed", draft([("tower", "09:00", "17:30")])) == []
    issues = check("relaxed", draft([("tower", "09:00", "17:45")]))
    assert codes(issues) == ["emphasis-ends-late"]


def test_relaxed_daily_walking_limit_counts_transit_walking() -> None:
    d = draft([("tower", "09:00", "10:00"), ("museum", "10:30", "12:00"), ("lake", "13:00", "15:00")])
    ok = {("tower", "museum"): walk(10, 800), ("museum", "lake"): transit(30, 1200)}
    assert check("relaxed", d, ok) == []
    too_far = {("tower", "museum"): walk(10, 800), ("museum", "lake"): transit(30, 1300)}
    issues = check("relaxed", d, too_far)
    assert codes(issues) == ["emphasis-walk-too-far"]
    assert "2100 米" in issues[0].message


def test_relaxed_unknown_walking_is_a_warning() -> None:
    d = draft([("tower", "09:00", "10:00"), ("museum", "10:30", "12:00")])
    issues = check("relaxed", d, {("tower", "museum"): transit(20, None)})
    assert codes(issues) == ["emphasis-walk-unknown"] and issues[0].level == "warning"


# ---------- 深度文化 ----------


def test_culture_stay_at_least_recommended() -> None:
    # 测试景点建议游玩 120 分钟
    assert check("culture", draft([("tower", "09:00", "11:00")])) == []
    issues = check("culture", draft([("tower", "09:00", "10:30")]))
    assert codes(issues) == ["emphasis-stay-short"]
    assert "90 分钟" in issues[0].message and "120 分钟" in issues[0].message


def test_culture_unknown_duration_is_not_judged() -> None:
    unknown = p("old", ["历史"], recommendedDurationMinutes={"value": None, "verification": "todo", "todo": "TODO(Cecilia): 测试"})
    base = select_candidates([unknown], TravelerPreferences(days=1))
    c = candidates_for(EMPHASES["culture"], base, [unknown])
    issues = check_emphasis(EMPHASES["culture"], draft([("old", "09:00", "09:30")]), candidates=c, legs={}, frame=FRAME)
    assert issues == []


# ---------- 合进校验结果 ----------


def test_merge_issues_recomputes_status() -> None:
    passed = ValidationReport(status="passed", issues=[])
    err = ValidationIssue(level="error", code="emphasis-ends-late", message="测试")
    warn = ValidationIssue(level="warning", code="emphasis-walk-unknown", message="测试")
    assert merge_issues(passed, []).status == "passed"
    assert merge_issues(passed, [warn]).status == "warning"
    merged = merge_issues(ValidationReport(status="warning", issues=[warn]), [err])
    assert merged.status == "failed" and len(merged.issues) == 2
