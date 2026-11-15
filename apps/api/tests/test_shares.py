"""分享链接的测试（板块 7）。用临时数据库，行程是虚构的测试数据。

规则（2026-11-15 Cecilia 定）：
- 只有通过校验或只有警告的版本能分享；没通过的不展示，也不能分享。
- 同一个版本再分享一次，给回同一个链接。
- 链接可以撤回；撤回后打开显示"已撤回"。撤回后再分享，换一个新链接，旧链接仍然是撤回状态。
- 链接是 8 位随机小写字母和数字，不带名字和日期。
- 链接指向固定的版本：同一份行程以后加了新版本，分享页还是原来那一版。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.planning import get_itineraries
from app.api.shares import get_share_links
from app.main import app
from app.repositories.itinerary_repository import SqliteItineraryRepository
from app.repositories.share_link_repository import SLUG_ALPHABET, SLUG_LENGTH, SqliteShareLinkRepository
from tests.test_itinerary_storage import version_data

SLUG_RE = re.compile(rf"^[{SLUG_ALPHABET}]{{{SLUG_LENGTH}}}$")


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "t.db"


@pytest.fixture
def client(db: Path) -> Iterator[TestClient]:
    app.dependency_overrides[get_itineraries] = lambda: SqliteItineraryRepository(db)
    app.dependency_overrides[get_share_links] = lambda: SqliteShareLinkRepository(db)
    yield TestClient(app)
    app.dependency_overrides.clear()


def add_version(db: Path, status: str = "warning", title: str = "测试行程", itinerary_id: str | None = None) -> tuple[str, str]:
    repo = SqliteItineraryRepository(db)
    itin = itinerary_id or repo.create_itinerary("conv_x")
    return itin, repo.add_version(itin, version_data(status, title=title)).id


# ---- repository ----


def test_repository_create_find_revoke(db: Path) -> None:
    _, ver = add_version(db)
    repo = SqliteShareLinkRepository(db)
    assert repo.active_for_version(ver) is None

    link = repo.create(ver)
    assert SLUG_RE.match(link.slug) and link.versionId == ver and link.revokedAt is None
    assert repo.get(link.slug) == link
    assert repo.active_for_version(ver) == link

    revoked = repo.revoke(link.slug)
    assert revoked is not None and revoked.revokedAt is not None
    assert repo.get(link.slug).revokedAt is not None  # type: ignore[union-attr]
    assert repo.active_for_version(ver) is None
    # 撤回两次不改第一次的时间
    assert repo.revoke(link.slug).revokedAt == revoked.revokedAt  # type: ignore[union-attr]
    assert repo.get("nope0000") is None and repo.revoke("nope0000") is None


def test_repository_active_links_by_version(db: Path) -> None:
    _, a = add_version(db)
    _, b = add_version(db)
    repo = SqliteShareLinkRepository(db)
    la = repo.create(a)
    lb = repo.create(b)
    repo.revoke(lb.slug)
    assert repo.active_by_version([a, b, "ver_nope"]) == {a: la}
    assert repo.active_by_version([]) == {}


def test_slugs_are_random(db: Path) -> None:
    repo = SqliteShareLinkRepository(db)
    slugs = set()
    for _ in range(20):
        _, ver = add_version(db)
        slugs.add(repo.create(ver).slug)
    assert len(slugs) == 20 and all(SLUG_RE.match(s) for s in slugs)


def test_slug_collision_is_retried(db: Path) -> None:
    _, a = add_version(db)
    _, b = add_version(db)
    picks = iter(["aaaaaaaa", "aaaaaaaa", "bbbbbbbb"])
    repo = SqliteShareLinkRepository(db, make_slug=lambda: next(picks))
    assert repo.create(a).slug == "aaaaaaaa"
    assert repo.create(b).slug == "bbbbbbbb"


# ---- 接口 ----


def test_publish_then_open(client: TestClient, db: Path) -> None:
    _, ver = add_version(db, "warning", title="武汉一日测试")
    r = client.post(f"/api/itinerary-versions/{ver}/share")
    assert r.status_code == 201
    link = r.json()
    assert SLUG_RE.match(link["slug"]) and link["versionId"] == ver and link["path"] == f"/s/{link['slug']}"
    assert link["revokedAt"] is None

    page = client.get(f"/api/share/{link['slug']}")
    assert page.status_code == 200
    body = page.json()
    assert body["slug"] == link["slug"] and body["version"]["id"] == ver
    assert body["version"]["title"] == "武汉一日测试"
    assert body["version"]["planner"]["provider"] == "qwen"
    assert body["version"]["validation"]["status"] == "warning"


def test_passed_version_can_be_shared(client: TestClient, db: Path) -> None:
    _, ver = add_version(db, "passed")
    assert client.post(f"/api/itinerary-versions/{ver}/share").status_code == 201


def test_sharing_twice_gives_the_same_link(client: TestClient, db: Path) -> None:
    _, ver = add_version(db)
    first = client.post(f"/api/itinerary-versions/{ver}/share")
    second = client.post(f"/api/itinerary-versions/{ver}/share")
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["slug"] == second.json()["slug"]


def test_failed_version_cannot_be_shared(client: TestClient, db: Path) -> None:
    _, ver = add_version(db, "failed")
    r = client.post(f"/api/itinerary-versions/{ver}/share")
    assert r.status_code == 409 and "没通过校验" in r.json()["detail"]


def test_unknown_version_and_slug(client: TestClient) -> None:
    assert client.post("/api/itinerary-versions/ver_nope/share").status_code == 404
    assert client.get("/api/share/nope0000").status_code == 404
    assert client.delete("/api/share/nope0000").status_code == 404


def test_revoke_then_share_again_gives_a_new_link(client: TestClient, db: Path) -> None:
    _, ver = add_version(db)
    old = client.post(f"/api/itinerary-versions/{ver}/share").json()["slug"]

    r = client.delete(f"/api/share/{old}")
    assert r.status_code == 200 and r.json()["revokedAt"] is not None
    gone = client.get(f"/api/share/{old}")
    assert gone.status_code == 410 and "撤回" in gone.json()["detail"]

    new = client.post(f"/api/itinerary-versions/{ver}/share")
    assert new.status_code == 201 and new.json()["slug"] != old
    assert client.get(f"/api/share/{old}").status_code == 410
    assert client.get(f"/api/share/{new.json()['slug']}").status_code == 200


def test_link_stays_on_its_version(client: TestClient, db: Path) -> None:
    """原行程以后再改（加新版本），分享页还是分享时那一版。"""
    itin, ver = add_version(db, title="第一版")
    slug = client.post(f"/api/itinerary-versions/{ver}/share").json()["slug"]
    add_version(db, title="第二版", itinerary_id=itin)
    body = client.get(f"/api/share/{slug}").json()
    assert body["version"]["id"] == ver and body["version"]["title"] == "第一版"
    assert body["version"]["versionNumber"] == 1


def test_create_returns_the_active_link_instead_of_a_second_one(db: Path) -> None:
    """两个请求同时分享同一个版本：数据库保证只有一个没撤回的链接。"""
    _, ver = add_version(db)
    repo = SqliteShareLinkRepository(db)
    first = repo.create(ver)
    again = repo.create(ver)
    assert again == first


def test_current_link_of_a_version(client: TestClient, db: Path) -> None:
    _, ver = add_version(db)
    assert client.get(f"/api/itinerary-versions/{ver}/share").status_code == 404
    slug = client.post(f"/api/itinerary-versions/{ver}/share").json()["slug"]
    assert client.get(f"/api/itinerary-versions/{ver}/share").json()["slug"] == slug
    client.delete(f"/api/share/{slug}")
    assert client.get(f"/api/itinerary-versions/{ver}/share").status_code == 404
