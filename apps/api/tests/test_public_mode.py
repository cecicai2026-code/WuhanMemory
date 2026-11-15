"""公开模式的测试（板块 7，2026-11-15 Cecilia 定，按推荐）。

公开模式在后端 .env 里打开（PUBLIC_MODE=true），本机开发时关着，一切照旧。打开后：
1. 第三方和官网占位照片不对外：景点接口不返回它们，后端也不提供 photos-placeholder 目录。
2. 我的行程、生成和撤回分享链接要口令（请求头 X-Owner-Passcode，口令在 .env 的 OWNER_PASSCODE）；
   没设口令时这些功能关掉。分享页本身谁都能打开。
3. 规划（发消息）和双模型对比限次数：同一个地址每小时、全站每天各有上限，对比一次算 2 次；带对口令的不限。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.planning import get_conversations, get_itineraries
from app.api.pois import get_data_dir, get_poi_repository, get_today
from app.api.shares import get_share_links
from app.api.trips import get_trip_lister
from app.core.site_policy import SitePolicy, get_rate_store, get_site_policy
from app.db.import_pois import import_pois
from app.db.sqlite import connect
from app.main import app
from app.repositories.conversation_repository import SqliteConversationRepository
from app.repositories.itinerary_repository import SqliteItineraryRepository
from app.repositories.poi_repository import SqlitePoiRepository
from app.repositories.rate_event_repository import SqliteRateEventRepository
from app.repositories.share_link_repository import SqliteShareLinkRepository
from app.schemas.poi import PoiFile
from app.services.poi_view import PoiPresenter
from app.services.trips import TripLister
from tests.poi_factory import good_poi, write_data_dir
from tests.test_itinerary_storage import version_data

PASS = "test-passcode-1234"
OWNER = {"X-Owner-Passcode": PASS}


def policy(**kw: object) -> SitePolicy:
    base: dict[str, object] = {"public_mode": True, "owner_passcode": PASS, "per_client_per_hour": 2, "per_day": 100}
    base.update(kw)
    return SitePolicy(**base)  # type: ignore[arg-type]


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "t.db"


@pytest.fixture
def make_client(db: Path) -> Iterator[object]:
    def make(p: SitePolicy) -> TestClient:
        app.dependency_overrides[get_site_policy] = lambda: p
        app.dependency_overrides[get_rate_store] = lambda: SqliteRateEventRepository(db)
        app.dependency_overrides[get_itineraries] = lambda: SqliteItineraryRepository(db)
        app.dependency_overrides[get_conversations] = lambda: SqliteConversationRepository(db)
        app.dependency_overrides[get_share_links] = lambda: SqliteShareLinkRepository(db)
        app.dependency_overrides[get_trip_lister] = lambda: TripLister(
            SqliteItineraryRepository(db), SqliteConversationRepository(db), SqliteShareLinkRepository(db)
        )
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


def add_version(db: Path) -> str:
    repo = SqliteItineraryRepository(db)
    return repo.add_version(repo.create_itinerary(SqliteConversationRepository(db).create().id), version_data()).id


# ---------- 口令 ----------


def test_owner_endpoints_need_the_passcode(make_client, db: Path) -> None:  # type: ignore[no-untyped-def]
    client = make_client(policy())
    ver = add_version(db)
    assert client.get("/api/trips").status_code == 401
    assert client.get("/api/trips", headers={"X-Owner-Passcode": "wrong"}).status_code == 401
    assert client.post(f"/api/itinerary-versions/{ver}/share").status_code == 401
    assert client.get(f"/api/itinerary-versions/{ver}/share").status_code == 401

    assert client.get("/api/trips", headers=OWNER).status_code == 200
    slug = client.post(f"/api/itinerary-versions/{ver}/share", headers=OWNER).json()["slug"]
    # 分享页谁都能打开
    assert client.get(f"/api/share/{slug}").status_code == 200
    assert client.delete(f"/api/share/{slug}").status_code == 401
    assert client.delete(f"/api/share/{slug}", headers=OWNER).status_code == 200


def test_401_says_what_to_do(make_client) -> None:  # type: ignore[no-untyped-def]
    r = make_client(policy()).get("/api/trips")
    assert r.status_code == 401 and "口令" in r.json()["detail"]


def test_no_passcode_set_closes_owner_endpoints(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(policy(owner_passcode=None))
    r = client.get("/api/trips", headers={"X-Owner-Passcode": ""})
    assert r.status_code == 403 and "OWNER_PASSCODE" in r.json()["detail"]


def test_local_mode_needs_nothing(make_client, db: Path) -> None:  # type: ignore[no-untyped-def]
    client = make_client(policy(public_mode=False))
    ver = add_version(db)
    assert client.get("/api/trips").status_code == 200
    assert client.post(f"/api/itinerary-versions/{ver}/share").status_code == 201


# ---------- 次数限制 ----------


def send(client: TestClient, headers: dict[str, str] | None = None) -> int:
    # 对话不存在：没超限时是 404（次数照样算），超限时是 429
    return client.post("/api/conversations/nope/messages", json={"content": "武汉一天"}, headers=headers or {}).status_code


def test_messages_are_limited_per_client(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(policy(per_client_per_hour=2))
    assert [send(client), send(client), send(client)] == [404, 404, 429]
    # 带对口令的不限
    assert send(client, OWNER) == 404


def test_429_says_when(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(policy(per_client_per_hour=1))
    send(client)
    r = client.post("/api/conversations/nope/messages", json={"content": "x"})
    assert r.status_code == 429 and "每小时" in r.json()["detail"]


def test_comparison_counts_twice(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(policy(per_client_per_hour=3))
    # 请求是空的：没超限时是 400（次数照样算 2 次）
    assert client.post("/api/comparisons", json={"request": " ", "emphasis": "classic"}).status_code == 400
    assert send(client) == 404
    assert send(client) == 429
    # 只剩 0 次，对比要 2 次
    assert client.post("/api/comparisons", json={"request": " ", "emphasis": "classic"}).status_code == 429


def test_local_mode_has_no_limit(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(policy(public_mode=False, per_client_per_hour=1))
    assert [send(client) for _ in range(3)] == [404, 404, 404]


def test_rate_store_counts_hour_and_day(db: Path) -> None:
    store = SqliteRateEventRepository(db)
    now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
    store.add("a", 1, now - timedelta(minutes=90))  # 一个多小时前：不算进每小时，算进当天
    store.add("a", 2, now - timedelta(minutes=10))
    store.add("b", 1, now - timedelta(minutes=5))
    assert store.used_by("a", since=now - timedelta(hours=1)) == 2
    assert store.used_by("b", since=now - timedelta(hours=1)) == 1
    assert store.used_total(since=now - timedelta(hours=3)) == 4


def test_daily_limit_is_shared(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(policy(per_client_per_hour=10, per_day=2, trust_proxy_headers=True))
    assert send(client, {"X-Forwarded-For": "1.1.1.1"}) == 404
    assert send(client, {"X-Forwarded-For": "2.2.2.2"}) == 404
    r = client.post("/api/conversations/nope/messages", json={"content": "x"}, headers={"X-Forwarded-For": "3.3.3.3"})
    assert r.status_code == 429 and "今天" in r.json()["detail"]


def test_client_address_is_not_stored_in_plain_text(make_client, db: Path) -> None:  # type: ignore[no-untyped-def]
    client = make_client(policy(trust_proxy_headers=True))
    send(client, {"X-Forwarded-For": "203.0.113.7"})
    conn = connect(db)
    rows = [tuple(r) for r in conn.execute("SELECT * FROM rate_events")]
    conn.close()
    assert rows and all("203.0.113.7" not in str(r) for r in rows)


# ---------- 占位照片 ----------


def data_with_placeholder(root: Path) -> Path:
    poi = good_poi("photo-sample")
    poi["photos"].append(
        {
            "file": "ph.jpg",
            "caption": "测试占位照片",
            "license": "third-party-placeholder",
            "sourceUrl": "https://example.com/ph.jpg",
            "retrievedAt": "2026-11-10",
            "licenseNote": "测试：第三方占位",
        }
    )
    data = write_data_dir(root / "data", [poi], {"photo-sample": ["sample.jpg"]})
    (data / "photos-placeholder" / "photo-sample").mkdir(parents=True)
    (data / "photos-placeholder" / "photo-sample" / "ph.jpg").write_bytes(b"test")
    return data


def test_presenter_hides_placeholder_photos(tmp_path: Path) -> None:
    data = data_with_placeholder(tmp_path)
    poi = PoiFile.model_validate_json((data / "pois" / "photo-sample.json").read_text(encoding="utf-8"))
    today = date(2026, 11, 15)
    shown = PoiPresenter(data, today).detail(poi).photos
    hidden = PoiPresenter(data, today, hide_placeholder_photos=True).detail(poi).photos
    assert [p.placeholder for p in shown] == [False, True]
    assert [p.placeholder for p in hidden] == [False]


def test_poi_api_hides_placeholder_photos_in_public_mode(make_client, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    data = data_with_placeholder(tmp_path)
    path = tmp_path / "pois.db"
    conn = connect(path)
    try:
        import_pois(conn, data, date(2026, 11, 15))
    finally:
        conn.close()

    def get_detail(p: SitePolicy) -> list[bool]:
        client = make_client(p)
        app.dependency_overrides[get_poi_repository] = lambda: SqlitePoiRepository(path)
        app.dependency_overrides[get_today] = lambda: date(2026, 11, 15)
        app.dependency_overrides[get_data_dir] = lambda: data
        return [ph["placeholder"] for ph in client.get("/api/pois/photo-sample").json()["poi"]["photos"]]

    assert get_detail(policy(public_mode=False)) == [False, True]
    assert get_detail(policy()) == [False]
