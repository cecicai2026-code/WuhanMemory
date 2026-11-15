"""我的行程（板块 7）的测试。用临时数据库，行程是虚构的测试数据。

规则（2026-11-15 Cecilia 定）：只列 /map 上生成的行程（属于某段对话的），按对话分组，新的在前；
每份行程列出它的全部版本，带有没有没撤回的分享链接。/compare 产生的行程（不属于对话）不列。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.planning import get_conversations, get_itineraries
from app.api.shares import get_share_links
from app.api.trips import get_trip_lister
from app.main import app
from app.repositories.conversation_repository import SqliteConversationRepository
from app.repositories.itinerary_repository import SqliteItineraryRepository
from app.repositories.share_link_repository import SqliteShareLinkRepository
from app.services.trips import TripLister
from tests.test_itinerary_storage import version_data


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "t.db"


@pytest.fixture
def client(db: Path) -> Iterator[TestClient]:
    app.dependency_overrides[get_itineraries] = lambda: SqliteItineraryRepository(db)
    app.dependency_overrides[get_conversations] = lambda: SqliteConversationRepository(db)
    app.dependency_overrides[get_share_links] = lambda: SqliteShareLinkRepository(db)
    app.dependency_overrides[get_trip_lister] = lambda: lister(db)
    yield TestClient(app)
    app.dependency_overrides.clear()


def lister(db: Path) -> TripLister:
    return TripLister(SqliteItineraryRepository(db), SqliteConversationRepository(db), SqliteShareLinkRepository(db))


def with_emphasis(status: str, emphasis: str | None, title: str = "测试行程"):  # type: ignore[no-untyped-def]
    data = version_data(status, title=title)
    data.emphasis = emphasis
    return data


def test_groups_by_conversation_newest_first(db: Path) -> None:
    convs = SqliteConversationRepository(db)
    itins = SqliteItineraryRepository(db)

    old = convs.create()
    convs.add_message(old.id, "user", "武汉一天，看博物馆")
    convs.add_message(old.id, "assistant", "排好了", kind="itinerary")
    convs.add_message(old.id, "user", "再轻松一点")
    a = itins.create_itinerary(old.id)
    itins.add_version(a, with_emphasis("warning", "classic", "第一版"))
    itins.add_version(a, with_emphasis("passed", "classic", "第二版"))

    new = convs.create()
    convs.add_message(new.id, "user", "武汉两天，喜欢历史")
    b = itins.create_itinerary(new.id)
    c = itins.create_itinerary(new.id)
    itins.add_version(b, with_emphasis("warning", "classic"))
    itins.add_version(c, with_emphasis("failed", "relaxed"))

    # /compare 产生的行程不属于任何对话，不列
    itins.add_version(itins.create_itinerary(None), with_emphasis("passed", "classic"))
    # 有对话但没生成行程（只反问过）的也不列
    convs.add_message(convs.create().id, "user", "想去武汉")

    trips = lister(db).list()
    assert [t.conversationId for t in trips] == [new.id, old.id]
    assert trips[0].request == "武汉两天，喜欢历史" and trips[1].request == "武汉一天，看博物馆"
    assert [i.emphasisLabel for i in trips[0].itineraries] == ["经典必去", "轻松少走路"]

    versions = trips[1].itineraries[0].versions
    assert [v.versionNumber for v in versions] == [2, 1]  # 新版本在前
    assert versions[0].title == "第二版" and versions[0].validationStatus == "passed"
    assert versions[0].days == 1 and versions[0].poiNames == ["测试景点a"]
    assert versions[0].providerLabel == "测试模型" and versions[0].share is None
    assert trips[0].itineraries[1].versions[0].validationStatus == "failed"


def test_share_link_shows_on_its_version(db: Path) -> None:
    convs = SqliteConversationRepository(db)
    itins = SqliteItineraryRepository(db)
    links = SqliteShareLinkRepository(db)
    conv = convs.create()
    itin = itins.create_itinerary(conv.id)
    v1 = itins.add_version(itin, with_emphasis("warning", "classic"))
    v2 = itins.add_version(itin, with_emphasis("warning", "classic"))
    link = links.create(v1.id)
    revoked = links.create(v2.id)
    links.revoke(revoked.slug)

    versions = {v.id: v for v in lister(db).list()[0].itineraries[0].versions}
    assert versions[v1.id].share is not None and versions[v1.id].share.path == f"/s/{link.slug}"  # type: ignore[union-attr]
    assert versions[v2.id].share is None


def test_old_version_without_emphasis(db: Path) -> None:
    """板块 5B 之前存的版本没有侧重。"""
    convs = SqliteConversationRepository(db)
    itins = SqliteItineraryRepository(db)
    conv = convs.create()
    itins.add_version(itins.create_itinerary(conv.id), with_emphasis("warning", None))
    item = lister(db).list()[0].itineraries[0]
    assert item.emphasis is None and item.emphasisLabel is None


def test_empty(db: Path) -> None:
    assert lister(db).list() == []


def test_trips_api(client: TestClient, db: Path) -> None:
    assert client.get("/api/trips").json() == []
    convs = SqliteConversationRepository(db)
    itins = SqliteItineraryRepository(db)
    conv = convs.create()
    convs.add_message(conv.id, "user", "武汉一天")
    ver = itins.add_version(itins.create_itinerary(conv.id), with_emphasis("passed", "culture"))
    slug = client.post(f"/api/itinerary-versions/{ver.id}/share").json()["slug"]

    body = client.get("/api/trips").json()
    assert body[0]["request"] == "武汉一天"
    item = body[0]["itineraries"][0]
    assert item["emphasisLabel"] == "深度文化"
    assert item["versions"][0]["id"] == ver.id and item["versions"][0]["share"]["slug"] == slug
