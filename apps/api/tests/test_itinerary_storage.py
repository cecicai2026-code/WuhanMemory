"""行程版本和对话存进 SQLite 的测试。用临时数据库文件，内容是虚构的测试数据。"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from app.repositories.conversation_repository import SqliteConversationRepository
from app.repositories.itinerary_repository import SqliteItineraryRepository
from app.schemas.itinerary import ItineraryVersionData
from app.schemas.planning import TravelerPreferences


def fact(value: Any, status: str = "pending") -> dict[str, Any]:
    return {
        "value": value,
        "verification": "placeholder",
        "status": status,
        "source": None,
        "lastCheckedAt": "2026-11-10",
        "expiresAt": "2027-02-08",
        "todo": None,
        "note": None,
    }


def version_data(status: str = "warning", provider: str = "qwen", title: str = "测试行程") -> ItineraryVersionData:
    issues = [] if status == "passed" else [
        {"level": "error" if status == "failed" else "warning", "code": "test", "message": "测试问题"}
    ]
    return ItineraryVersionData.model_validate(
        {
            "title": title,
            "frame": {"days": 1, "startDate": "2026-11-17", "pace": "moderate"},
            "preferences": {"days": 1},
            "defaultsUsed": ["节奏：适中（你没说，按默认）"],
            "days": [
                {
                    "dayNumber": 1,
                    "date": "2026-11-17",
                    "theme": "测试主题",
                    "stops": [
                        {
                            "poiId": "a",
                            "name": "测试景点a",
                            "district": "测试区",
                            "category": "museum",
                            "location": {"lng": 114.3, "lat": 30.55, "coordSystem": "GCJ-02"},
                            "arrive": "09:30",
                            "leave": "11:30",
                            "reason": "测试理由",
                            "facts": {
                                "openingHours": fact({"periods": [], "closedWeekdays": [1]}),
                                "reservation": fact({"required": True}),
                                "ticket": fact({"free": True}),
                                "payment": fact(None, "missing"),
                                "recommendedDurationMinutes": fact(120),
                            },
                        }
                    ],
                    "legs": [],
                }
            ],
            "validation": {"status": status, "issues": issues},
            "planner": {
                "provider": provider,
                "providerLabel": "测试模型",
                "model": "test-model-1",
                "rounds": 2 if status == "failed" else 1,
                "firstRoundStatus": status,
                "firstRoundErrors": 1 if status == "failed" else 0,
            },
            "draft": {"days": [{"dayNumber": 1, "stops": [{"poiId": "a", "arrive": "09:30", "leave": "11:30"}]}]},
            "dataAsOf": "2026-11-15",
        }
    )


def test_versions_are_numbered_and_round_trip(tmp_path: Path) -> None:
    repo = SqliteItineraryRepository(tmp_path / "t.db")
    itin = repo.create_itinerary("conv_x")
    v1 = repo.add_version(itin, version_data("warning", "qwen"))
    v2 = repo.add_version(itin, version_data("failed", "doubao", title="第二版"))
    assert (v1.versionNumber, v2.versionNumber) == (1, 2)

    got = repo.get_version(v2.id)
    assert got is not None
    assert got.title == "第二版" and got.planner.provider == "doubao" and got.planner.model == "test-model-1"
    assert got.validation.status == "failed" and got.validation.errors[0].message == "测试问题"
    assert got.days[0].stops[0].facts.payment.status == "missing"
    assert got.days[0].date == date(2026, 11, 17)
    assert [v.versionNumber for v in repo.list_versions(itin)] == [1, 2]
    assert repo.get_version("ver_nope") is None


def test_version_numbers_are_per_itinerary(tmp_path: Path) -> None:
    repo = SqliteItineraryRepository(tmp_path / "t.db")
    a, b = repo.create_itinerary(None), repo.create_itinerary(None)
    repo.add_version(a, version_data())
    assert repo.add_version(b, version_data()).versionNumber == 1


def test_summary_columns_for_comparison(tmp_path: Path) -> None:
    """板块 6 要按模型、校验结果、修正轮数统计，这几列单独存。"""
    db = tmp_path / "t.db"
    repo = SqliteItineraryRepository(db)
    itin = repo.create_itinerary(None)
    repo.add_version(itin, version_data("failed", "doubao"))
    row = sqlite3.connect(db).execute(
        "SELECT provider, model, validation_status, error_count, warning_count, rounds FROM itinerary_versions"
    ).fetchone()
    assert row == ("doubao", "test-model-1", "failed", 1, 0, 2)


def test_conversation_preferences_and_messages(tmp_path: Path) -> None:
    repo = SqliteConversationRepository(tmp_path / "t.db")
    conv = repo.create()
    assert repo.get(conv.id) is not None and repo.get(conv.id).preferences == TravelerPreferences()  # type: ignore[union-attr]

    repo.save_preferences(conv.id, TravelerPreferences(days=2, interests=["历史"], transport="metro"))
    repo.set_itinerary(conv.id, "itin_x")
    repo.add_message(conv.id, "user", "武汉两天")
    repo.add_message(conv.id, "assistant", "想玩几天？", kind="question", asked=["days", "date"], provider="qwen")
    repo.add_message(conv.id, "assistant", "排好了", kind="itinerary", provider="qwen", itinerary_version_id="ver_x")

    got = repo.get(conv.id)
    assert got is not None and got.preferences.days == 2 and got.itineraryId == "itin_x"
    msgs = repo.messages(conv.id)
    assert [m.role for m in msgs] == ["user", "assistant", "assistant"]
    assert msgs[1].asked == ["days", "date"] and msgs[0].asked == [] and msgs[0].kind is None
    assert msgs[2].kind == "itinerary" and msgs[2].provider == "qwen" and msgs[2].itineraryVersionId == "ver_x"


def test_added_columns_reach_an_old_table(tmp_path: Path) -> None:
    """dev 数据库里已经有不带 kind、asked 两列的旧表时，启动时补上。"""
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE conversation_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,"
        " role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL, provider TEXT, itinerary_version_id TEXT)"
    )
    conn.commit()
    conn.close()
    repo = SqliteConversationRepository(db)
    conv = repo.create()
    repo.add_message(conv.id, "assistant", "想玩几天？", kind="question", asked=["days"])
    assert repo.messages(conv.id)[0].asked == ["days"]
    assert repo.get("conv_nope") is None
