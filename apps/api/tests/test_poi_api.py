"""SQLite 导入、repository 和景点接口的测试。用的是 tests/fixtures/data 里的虚构数据。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.pois import get_data_dir, get_poi_repository, get_today
from app.db.import_pois import import_pois
from app.db.sqlite import connect
from app.main import app
from app.repositories.poi_repository import SqlitePoiRepository
from tests.poi_factory import TODAY, good_poi, write_data_dir

FIXTURES = Path(__file__).parent / "fixtures" / "data"
today = date.fromisoformat(TODAY)


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    conn = connect(path)
    try:
        import_pois(conn, FIXTURES, today)
    finally:
        conn.close()
    return path


@pytest.fixture()
def client(db_path: Path):
    app.dependency_overrides[get_poi_repository] = lambda: SqlitePoiRepository(db_path)
    app.dependency_overrides[get_today] = lambda: today
    app.dependency_overrides[get_data_dir] = lambda: FIXTURES
    # 不用 with，避免触发启动时导入真实的 data/
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_import_skips_pois_with_errors(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    try:
        report, imported = import_pois(conn, FIXTURES, today)
        facts = conn.execute("SELECT COUNT(*) FROM poi_facts WHERE poi_id = 'good-sample'").fetchone()[0]
    finally:
        conn.close()
    # 只有合格的样例和"已过期"（警告不挡导入）能进数据库
    assert sorted(imported) == ["broken-expired", "good-sample"]
    assert not report.ok
    assert facts == 12  # 11 条必填信息 + 1 个拍照机位


def test_import_rebuilds_table(tmp_path: Path) -> None:
    data = write_data_dir(tmp_path / "data", [good_poi("a-place"), good_poi("b-place")], {"a-place": ["sample.jpg"], "b-place": ["sample.jpg"]})
    conn = connect(tmp_path / "t.db")
    try:
        import_pois(conn, data, today)
        (data / "pois" / "b-place.json").unlink()
        _, imported = import_pois(conn, data, today)
        count = conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0]
    finally:
        conn.close()
    assert imported == ["a-place"] and count == 1


def test_repository_filters(db_path: Path) -> None:
    repo = SqlitePoiRepository(db_path)
    assert [p.id for p in repo.list_pois()] == ["broken-expired", "good-sample"]
    assert repo.list_pois(district="没有这个区") == []
    assert repo.get_poi("good-sample") is not None
    assert repo.get_poi("broken-no-location") is None


def test_list_pois(client: TestClient) -> None:
    res = client.get("/api/pois")
    assert res.status_code == 200
    body = res.json()
    assert body["asOf"] == TODAY
    by_id = {p["id"]: p for p in body["pois"]}
    assert set(by_id) == {"broken-expired", "good-sample"}
    assert by_id["good-sample"]["status"] == "pending"
    assert by_id["broken-expired"]["status"] == "expired"
    assert by_id["good-sample"]["location"]["coordSystem"] == "GCJ-02"
    assert by_id["good-sample"]["coverPhoto"]["url"] == "/media/photos/good-sample/sample.jpg"


def test_get_poi_detail_statuses(client: TestClient) -> None:
    res = client.get("/api/pois/good-sample")
    assert res.status_code == 200
    poi = res.json()["poi"]
    assert poi["address"]["status"] == "verified"  # onsite
    assert poi["location"]["lng"] == 114.30
    assert poi["intro"]["status"] == "pending"  # placeholder
    assert poi["history"]["status"] == "missing"  # todo
    assert poi["ticket"]["source"]["type"] == "field-visit"
    assert poi["openingHours"]["lastCheckedAt"] == "2026-11-10"
    assert poi["openingHours"]["expiresAt"] == "2027-02-08"
    assert poi["counts"] == {"verified": 6, "pending": 3, "expired": 0, "missing": 3}


def test_expired_fact_status(client: TestClient) -> None:
    poi = client.get("/api/pois/broken-expired").json()["poi"]
    assert poi["reservation"]["status"] == "expired"


def test_status_changes_with_date(client: TestClient) -> None:
    """同一份数据，过了过期日再请求，状态就变成已过期，不是写死的。"""
    app.dependency_overrides[get_today] = lambda: date(2027, 3, 1)
    poi = client.get("/api/pois/good-sample").json()["poi"]
    assert poi["openingHours"]["status"] == "expired"
    assert poi["status"] == "expired"


def test_unknown_poi_404(client: TestClient) -> None:
    res = client.get("/api/pois/not-a-place")
    assert res.status_code == 404


def test_district_filter(client: TestClient) -> None:
    assert len(client.get("/api/pois", params={"district": "测试区"}).json()["pois"]) == 2
    assert client.get("/api/pois", params={"district": "别的区"}).json()["pois"] == []
