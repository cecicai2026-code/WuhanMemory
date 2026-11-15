"""方案的数字、"几乎一样"的判断和方案之间比较的测试（板块 5B）。

全部是虚构的测试数据（景点名"测试景点x"），票价也是编的测试值，不是真实景点信息。
"""

from __future__ import annotations

from typing import Any

from app.schemas.itinerary import ItineraryVersionData
from app.schemas.planning import PlanDraft
from app.services.planning.metrics import compare_plans, near_duplicate, plan_metrics


def fact(value: Any, status: str = "verified") -> dict[str, Any]:
    return {
        "value": value,
        "verification": "todo" if status == "missing" else "confirmed",
        "status": status,
        "source": None,
        "lastCheckedAt": None,
        "expiresAt": None,
        "todo": None,
        "note": None,
    }


def stop(poi_id: str, arrive: str, leave: str, *, ticket: Any = "free") -> dict[str, Any]:
    if ticket == "free":
        ticket_fact = fact({"free": True})
    elif ticket is None:
        ticket_fact = fact(None, "missing")
    else:
        ticket_fact = fact(ticket)
    return {
        "poiId": poi_id,
        "name": f"测试景点{poi_id}",
        "district": "测试区",
        "category": "museum",
        "location": {"lng": 114.3, "lat": 30.55, "coordSystem": "GCJ-02"},
        "arrive": arrive,
        "leave": leave,
        "reason": "测试理由",
        "facts": {
            "openingHours": fact({"allDay": True}),
            "reservation": fact({"required": False}),
            "ticket": ticket_fact,
            "payment": fact({"methods": ["wechat"]}),
            "recommendedDurationMinutes": fact(60),
        },
    }


def leg(a: str, b: str, minutes: int | None, *, mode: str = "transit", meters: int | None = 1000, walking: int | None = None) -> dict[str, Any]:
    route: dict[str, Any] = {"mode": mode, "status": "ok" if minutes is not None else "error"}
    if minutes is not None:
        route["durationMinutes"] = minutes
        route["distanceMeters"] = meters
        route["walkingDistanceMeters"] = walking
    return {"fromPoiId": a, "toPoiId": b, "route": route, "choice": "测试"}


def version(
    *days: tuple[list[dict[str, Any]], list[dict[str, Any]]],
    start: str | None = "2026-11-17",
    issues: list[dict[str, Any]] | None = None,
    rounds: int = 1,
) -> ItineraryVersionData:
    from datetime import date, timedelta

    issues = issues or []
    status = "failed" if any(i["level"] == "error" for i in issues) else ("warning" if issues else "passed")
    first = date.fromisoformat(start) if start else None
    return ItineraryVersionData.model_validate(
        {
            "title": "测试方案",
            "frame": {"days": len(days), "startDate": start, "pace": "moderate"},
            "preferences": {"days": len(days)},
            "days": [
                {
                    "dayNumber": n,
                    "date": (first + timedelta(days=n - 1)).isoformat() if first else None,
                    "theme": "测试",
                    "stops": stops,
                    "legs": legs,
                }
                for n, (stops, legs) in enumerate(days, start=1)
            ],
            "validation": {"status": status, "issues": issues},
            "planner": {
                "provider": "qwen",
                "providerLabel": "通义千问",
                "model": "test-model",
                "rounds": rounds,
                "firstRoundStatus": status,
                "firstRoundErrors": 0,
            },
            "draft": {"title": "测试方案", "days": []},
            "dataAsOf": "2026-11-15",
        }
    )


def draft(*days: list[tuple[str, str, str]]) -> PlanDraft:
    return PlanDraft.model_validate(
        {
            "days": [
                {"dayNumber": n, "stops": [{"poiId": p, "arrive": a, "leave": b} for p, a, b in stops]}
                for n, stops in enumerate(days, start=1)
            ]
        }
    )


# ---------- 交通和步行距离 ----------


def test_transport_minutes_by_mode() -> None:
    v = version(
        (
            [stop("a", "09:00", "10:00"), stop("b", "10:20", "11:00"), stop("c", "12:00", "13:00"), stop("d", "13:40", "15:00")],
            [leg("a", "b", 12, mode="walk", meters=900), leg("b", "c", 40, walking=600), leg("c", "d", 25, mode="drive", meters=8000)],
        )
    )
    m = plan_metrics(v)
    assert m.transportMinutes == 77
    assert m.minutesByMode == {"walk": 12, "transit": 40, "drive": 25}
    assert m.unknownLegs == 0
    # 步行段全程 900 米 + 公交换乘步行 600 米；打车不算步行
    assert m.walkingMeters == 1500 and m.walkingUnknownLegs == 0
    assert m.days[0].end == "15:00" and m.days[0].walkingMeters == 1500


def test_walk_leg_uses_walking_distance_when_given() -> None:
    v = version(([stop("a", "09:00", "10:00"), stop("b", "10:20", "11:00")], [leg("a", "b", 12, mode="walk", meters=900, walking=950)]))
    assert plan_metrics(v).walkingMeters == 950


def test_unknown_legs_are_counted_not_guessed() -> None:
    v = version(
        (
            [stop("a", "09:00", "10:00"), stop("b", "11:00", "12:00"), stop("c", "13:00", "14:00")],
            # 第一段没查到；第二段是旧缓存，公交没有换乘步行距离
            [leg("a", "b", None), leg("b", "c", 30, walking=None)],
        )
    )
    m = plan_metrics(v)
    assert m.transportMinutes == 30 and m.unknownLegs == 1
    assert m.walkingMeters == 0 and m.walkingUnknownLegs == 2


def test_missing_leg_counts_as_unknown() -> None:
    # 两站之间没有 leg（例如景点不存在没查路线）
    v = version(([stop("a", "09:00", "10:00"), stop("b", "11:00", "12:00")], []))
    m = plan_metrics(v)
    assert m.unknownLegs == 1 and m.walkingUnknownLegs == 1


# ---------- 门票 ----------

DAY_NIGHT = {
    "free": False,
    "items": [
        {"name": "日场全票", "priceCny": 70},
        {"name": "日场半票", "priceCny": 35},
        {"name": "夜场成人票（周五至周日及法定节假日）", "priceCny": 150},
        {"name": "夜场成人票（周一至周四）", "priceCny": 120},
    ],
}


def test_free_counts_zero_even_with_paid_extras() -> None:
    # 免费入园，另有收费的观光车：不算
    v = version(([stop("a", "09:00", "10:00", ticket={"free": True, "items": [{"name": "观光车", "priceCny": 30}]})], []))
    m = plan_metrics(v)
    assert m.ticketMinCny == 0 and m.ticketMaxCny == 0 and m.ticketComplete
    assert m.tickets[0].label == "免费"


def test_day_ticket_uses_adult_full_price() -> None:
    v = version(([stop("a", "09:00", "11:00", ticket=DAY_NIGHT)], []))
    t = plan_metrics(v).tickets[0]
    assert (t.minCny, t.maxCny) == (70, 70)
    assert t.label == "日场全票 70 元"


def test_adult_ticket_skips_half_price_listed_first() -> None:
    ticket = {"free": False, "items": [{"name": "学生半票", "priceCny": 20}, {"name": "成人票", "priceCny": 40}]}
    v = version(([stop("a", "09:00", "11:00", ticket=ticket)], []))
    assert plan_metrics(v).tickets[0].minCny == 40


def test_night_ticket_after_seven_matches_weekday() -> None:
    # 2026-11-17 是周二；2026-11-20 是周五
    tue = plan_metrics(version(([stop("a", "19:30", "21:00", ticket=DAY_NIGHT)], []), start="2026-11-17")).tickets[0]
    fri = plan_metrics(version(([stop("a", "19:30", "21:00", ticket=DAY_NIGHT)], []), start="2026-11-20")).tickets[0]
    assert (tue.minCny, tue.maxCny) == (120, 120)
    assert (fri.minCny, fri.maxCny) == (150, 150)
    assert "夜场" in tue.label


def test_night_ticket_without_date_is_a_range() -> None:
    m = plan_metrics(version(([stop("a", "19:30", "21:00", ticket=DAY_NIGHT)], []), start=None))
    t = m.tickets[0]
    assert (t.minCny, t.maxCny) == (120, 150)
    assert "120 或 150 元" in t.label
    assert (m.ticketMinCny, m.ticketMaxCny) == (120, 150)


def test_unknown_ticket_makes_total_incomplete() -> None:
    v = version(
        (
            [
                stop("a", "09:00", "10:00", ticket=DAY_NIGHT),
                stop("b", "11:00", "12:00", ticket=None),
                stop("c", "13:00", "14:00", ticket={"free": False, "items": []}),
            ],
            [],
        )
    )
    m = plan_metrics(v)
    assert m.ticketMinCny == 70 and not m.ticketComplete
    assert [t.label for t in m.tickets[1:]] == ["不详", "不详"]


# ---------- 校验和景点 ----------


def test_places_and_validation_counts() -> None:
    v = version(
        ([stop("a", "09:00", "10:00")], []),
        ([stop("b", "09:00", "10:00"), stop("c", "11:00", "12:00")], [leg("b", "c", 20, walking=300)]),
        issues=[{"level": "warning", "code": "x", "message": "测试"}, {"level": "warning", "code": "y", "message": "测试"}],
        rounds=2,
    )
    m = plan_metrics(v)
    assert m.poiIds == ["a", "b", "c"] and m.poiNames == ["测试景点a", "测试景点b", "测试景点c"]
    assert m.stopCount == 3
    assert [d.end for d in m.days] == ["10:00", "12:00"]
    assert (m.validationStatus, m.errorCount, m.warningCount, m.rounds) == ("warning", 0, 2, 2)


# ---------- 几乎一样 ----------


def test_same_places_and_close_end_times_are_near_duplicates() -> None:
    a = draft([("x", "09:00", "11:00"), ("y", "12:00", "16:00")])
    b = draft([("y", "09:00", "12:00"), ("x", "13:00", "16:40")])
    reason = near_duplicate(a, b)
    assert reason is not None and "景点相同" in reason


def test_one_swapped_place_is_still_near_duplicate() -> None:
    a = draft([("x", "09:00", "11:00"), ("y", "12:00", "16:00")])
    b = draft([("x", "09:00", "11:00"), ("z", "12:00", "16:30")])
    reason = near_duplicate(a, b)
    assert reason is not None and "只差 1 个" in reason


def test_two_different_places_are_not_duplicates() -> None:
    a = draft([("x", "09:00", "11:00"), ("y", "12:00", "16:00")])
    b = draft([("z", "09:00", "11:00"), ("w", "12:00", "16:00")])
    assert near_duplicate(a, b) is None


def test_end_time_an_hour_apart_is_not_duplicate() -> None:
    a = draft([("x", "09:00", "11:00"), ("y", "12:00", "16:00")])
    b = draft([("x", "09:00", "11:00"), ("y", "12:00", "17:00")])
    assert near_duplicate(a, b) is None


def test_every_day_must_end_close() -> None:
    a = draft([("x", "09:00", "11:00")], [("y", "09:00", "15:00")])
    b = draft([("x", "09:00", "11:30")], [("y", "09:00", "17:00")])
    assert near_duplicate(a, b) is None


def test_different_day_count_is_not_duplicate() -> None:
    a = draft([("x", "09:00", "11:00")])
    b = draft([("x", "09:00", "11:00")], [])
    assert near_duplicate(a, b) is None


# ---------- 比较表 ----------


def _two() -> list[ItineraryVersionData]:
    a = version(([stop("a", "09:00", "11:00", ticket=DAY_NIGHT), stop("b", "11:30", "13:00")], [leg("a", "b", 20, walking=400)]))
    b = version(
        (
            [stop("a", "09:00", "11:00", ticket=DAY_NIGHT), stop("c", "12:00", "13:00", ticket=None), stop("d", "13:20", "17:30")],
            [leg("a", "c", 45, walking=800), leg("c", "d", 10, mode="walk", meters=700)],
        ),
        issues=[{"level": "warning", "code": "x", "message": "测试"}],
    )
    return [a, b]


def test_comparison_table_rows() -> None:
    cmp = compare_plans(["经典必去", "深度文化"], _two())
    rows = {r.key: r for r in cmp.rows}
    assert cmp.labels == ["经典必去", "深度文化"]
    assert rows["places"].texts == ["测试景点a、测试景点b", "测试景点a、测试景点c、测试景点d"]
    assert rows["transportMinutes"].values == [20, 55]
    assert rows["transportMinutes"].texts == ["20 分钟", "55 分钟"]
    assert rows["byMode"].texts == ["公交地铁 20 分钟", "步行 10 分钟、公交地铁 45 分钟"]
    assert rows["walkingMeters"].values == [400, 1500]
    assert rows["walkingMeters"].texts == ["400 米", "1.5 公里"]
    assert rows["tickets"].texts == ["70 元", "70 元（不完整：测试景点c 票价不详）"]
    assert rows["end-day-1"].texts == ["13:00", "17:30"]
    assert rows["validation"].texts == ["通过", "有警告：0 条错误、1 条警告"]


def test_unknown_transport_is_noted() -> None:
    a, b = _two()
    b.days[0].legs[0].route.status = "error"
    b.days[0].legs[0].route.durationMinutes = None
    cmp = compare_plans(["A", "B"], [a, b])
    row = next(r for r in cmp.rows if r.key == "transportMinutes")
    assert row.texts[1] == "10 分钟（1 段没查到）"


def test_ticket_range_is_shown() -> None:
    night = version(([stop("a", "19:30", "21:00", ticket=DAY_NIGHT)], []), start=None)
    cmp = compare_plans(["A"], [night])
    assert next(r for r in cmp.rows if r.key == "tickets").texts == ["120 或 150 元"]


def test_end_rows_follow_longest_plan() -> None:
    a = version(([stop("a", "09:00", "11:00")], []))
    b = version(([stop("b", "09:00", "12:00")], []), ([stop("c", "09:00", "15:00")], []))
    cmp = compare_plans(["A", "B"], [a, b])
    rows = {r.key: r for r in cmp.rows}
    assert rows["end-day-2"].texts == ["—", "15:00"]
