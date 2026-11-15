"""路线服务的测试。不联网：高德的返回是按文档结构手写的假数据（坐标、线路名都是虚构的），
测的是解析、缓存和出错时的处理，不是真实路线。"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.pois import get_poi_repository
from app.api.routing import get_route_cache, get_route_provider
from app.data_quality.rules import CITY_TZ
from app.db.import_pois import import_pois
from app.db.sqlite import connect
from app.main import app
from app.repositories.poi_repository import SqlitePoiRepository
from app.repositories.route_cache_repository import SqliteRouteCacheRepository
from app.schemas.route import GeoPointOut, RoutePlace
from app.services.routing.amap import AmapRouteProvider, ProviderRoute, RouteProviderError, collect_polyline, parse_route
from app.services.routing.service import RouteService
from tests.poi_factory import TODAY

FIXTURES = Path(__file__).parent / "fixtures" / "data"
NOW = datetime(2026, 11, 15, 21, 30, tzinfo=CITY_TZ)

WALK_OK = {
    "status": "1", "info": "OK", "infocode": "10000",
    "route": {"paths": [{"distance": "700", "cost": {"duration": "560"},
                         "steps": [{"polyline": "114.300000,30.540000;114.301000,30.541000"},
                                   {"polyline": "114.301000,30.541000;114.302000,30.542000"}]}]},
}
DRIVE_OK = {
    "status": "1", "info": "OK", "infocode": "10000",
    "route": {"taxi_cost": "23", "paths": [{"distance": "8000", "cost": {"duration": "1500", "tolls": "0"},
                                            "steps": [{"polyline": "114.3,30.5;114.4,30.6"}]}]},
}
TRANSIT_OK = {
    "status": "1", "info": "OK", "infocode": "10000",
    "route": {"transits": [{
        "distance": "9000", "cost": {"duration": "2400", "transit_fee": "4.0"},
        "segments": [
            {"walking": {"steps": [{"polyline": {"polyline": "114.30,30.54;114.31,30.55"}}]},
             "bus": {"buslines": [
                 {"name": "测试地铁1号线(甲站--乙站)", "polyline": {"polyline": "114.31,30.55;114.35,30.56"}},
                 {"name": "备选公交(不应该被画出来)", "polyline": {"polyline": "100,10;101,11"}}]}},
            {"bus": {"buslines": [{"name": "测试地铁2号线（丙站--丁站）", "polyline": "114.35,30.56;114.36,30.57"}]}},
        ]}]},
}
TRANSIT_NONE = {"status": "1", "info": "OK", "infocode": "10000", "route": {"transits": []}}


def err(code: str, info: str) -> dict:
    return {"status": "0", "info": info, "infocode": code}


# ---------- 解析 ----------

def test_parse_walk() -> None:
    r = parse_route("walk", WALK_OK)
    assert r.status == "ok" and r.distanceMeters == 700 and r.durationMinutes == 9
    assert r.cost and r.cost.kind == "free" and r.cost.amountCny == 0
    assert len(r.polyline) == 4 and r.polyline[0].lng == 114.3


def test_parse_drive_taxi_cost_is_string() -> None:
    r = parse_route("drive", DRIVE_OK)
    assert r.cost and r.cost.kind == "taxi" and r.cost.amountCny == 23
    assert r.durationMinutes == 25


def test_parse_transit_lines_and_only_first_busline() -> None:
    r = parse_route("transit", TRANSIT_OK)
    assert r.summary == "测试地铁1号线 → 测试地铁2号线"
    assert r.cost and r.cost.kind == "fare" and r.cost.amountCny == 4
    assert r.durationMinutes == 40
    assert all(p.lng > 110 for p in r.polyline)  # 备选线路没画进来
    assert len(r.polyline) == 6


def test_walking_distance_by_mode() -> None:
    # 步行：全程都是走路；打车：不走路
    assert parse_route("walk", WALK_OK).walkingDistanceMeters == 700
    assert parse_route("drive", DRIVE_OK).walkingDistanceMeters == 0


def test_transit_walking_distance_from_amap_field() -> None:
    payload = copy.deepcopy(TRANSIT_OK)
    payload["route"]["transits"][0]["walking_distance"] = "1535"
    assert parse_route("transit", payload).walkingDistanceMeters == 1535


def test_transit_walking_distance_falls_back_to_segments() -> None:
    payload = copy.deepcopy(TRANSIT_OK)
    segs = payload["route"]["transits"][0]["segments"]
    segs[0]["walking"]["distance"] = "300"
    segs[1]["walking"] = {"distance": "250"}
    assert parse_route("transit", payload).walkingDistanceMeters == 550
    # 两样都没有：不知道，不猜
    assert parse_route("transit", TRANSIT_OK).walkingDistanceMeters is None


def test_parse_transit_none() -> None:
    r = parse_route("transit", TRANSIT_NONE)
    assert r.status == "none" and r.reason and "步行" in r.reason


@pytest.mark.parametrize(
    ("code", "words"),
    [("10001", "key 不正确"), ("10009", "不是 Web 服务"), ("10003", "次数用完"), ("10021", "限流"), ("99999", "99999")],
)
def test_parse_errors(code: str, words: str) -> None:
    with pytest.raises(RouteProviderError) as e:
        parse_route("walk", err(code, "SOMETHING"))
    assert words in e.value.message


def test_collect_polyline_skips_bad_points() -> None:
    assert len(collect_polyline({"polyline": "1,2;bad;3,4;5"})) == 2


# ---------- 发给高德的请求 ----------

def provider_with(responses: list[dict], seen: list[httpx.Request]) -> tuple[AmapRouteProvider, httpx.AsyncClient]:
    it = iter(responses)

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json=next(it))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AmapRouteProvider("k", "https://restapi.amap.com", client, gap_seconds=0, retry_seconds=0), client


A = GeoPointOut(lng=114.3024671, lat=30.544649)
B = GeoPointOut(lng=114.298068, lat=30.547412)


async def test_transit_request_params() -> None:
    seen: list[httpx.Request] = []
    p, client = provider_with([TRANSIT_OK], seen)
    async with client:
        await p.plan("transit", A, B, NOW.replace(hour=10, minute=0))
    q = seen[0].url.params
    assert seen[0].url.path == "/v5/direction/transit/integrated"
    assert q["origin"] == "114.302467,30.544649"  # 最多 6 位小数
    assert q["city1"] == q["city2"] == "027"
    assert q["date"] == "2026-11-15" and q["time"] == "10-00"
    assert q["show_fields"] == "cost,polyline"


async def test_qps_limit_retries_once() -> None:
    seen: list[httpx.Request] = []
    p, client = provider_with([err("10021", "CUQPS_HAS_EXCEEDED_THE_LIMIT"), WALK_OK], seen)
    async with client:
        r = await p.plan("walk", A, B, NOW)
    assert r.status == "ok" and len(seen) == 2


async def test_missing_key() -> None:
    async with httpx.AsyncClient() as client:
        p = AmapRouteProvider(None, "https://restapi.amap.com", client)
        with pytest.raises(RouteProviderError) as e:
            await p.plan("walk", A, B, NOW)
    assert e.value.code == "amap-key-missing"


# ---------- 缓存 ----------

class FakeProvider:
    name = "amap"

    def __init__(self) -> None:
        self.calls = 0
        self.fail: RouteProviderError | None = None

    async def plan(self, mode, origin, destination, depart_at) -> ProviderRoute:
        self.calls += 1
        self.depart_at = depart_at
        if self.fail:
            raise self.fail
        return parse_route(mode, {"walk": WALK_OK, "drive": DRIVE_OK, "transit": TRANSIT_OK}[mode])


class Clock:
    def __init__(self, t: datetime) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    conn = connect(path)
    try:
        import_pois(conn, FIXTURES, datetime.fromisoformat(TODAY).date())
    finally:
        conn.close()
    return path


def place(pid: str, lng: float) -> RoutePlace:
    return RoutePlace(id=pid, name=pid, location=GeoPointOut(lng=lng, lat=30.5))


def make_service(db_path: Path, provider: FakeProvider, clock: Clock) -> RouteService:
    return RouteService(SqlitePoiRepository(db_path), provider, SqliteRouteCacheRepository(db_path), clock)


async def test_cache_fresh_then_cached_then_expired(db_path: Path) -> None:
    prov, clock = FakeProvider(), Clock(NOW)
    svc = make_service(db_path, prov, clock)
    a, b = place("a", 114.3), place("b", 114.4)

    first = await svc.route(a, b, "drive")
    assert first.cache == "fresh" and first.checkedAt == NOW and first.expiresAt == NOW + timedelta(days=1)
    # 公交和驾车都按当天上午 10 点出发查
    assert prov.depart_at.hour == 10 and prov.depart_at.date() == NOW.date()

    clock.t = NOW + timedelta(hours=23)
    second = await svc.route(a, b, "drive")
    assert second.cache == "cached" and second.checkedAt == NOW and prov.calls == 1

    clock.t = NOW + timedelta(days=1, minutes=1)
    third = await svc.route(a, b, "drive")
    assert third.cache == "fresh" and third.checkedAt == clock.t and prov.calls == 2


async def test_new_routes_carry_walking_distance(db_path: Path) -> None:
    svc = make_service(db_path, FakeProvider(), Clock(NOW))
    r = await svc.route(place("a", 114.3), place("b", 114.4), "walk")
    assert r.walkingDistanceMeters == 700
    assert svc.cache.get("a", "b", "walk").route.walkingDistanceMeters == 700  # type: ignore[union-attr]


def test_old_cache_rows_get_walking_distance_from_raw(db_path: Path) -> None:
    from app.repositories.route_cache_repository import CachedRoute
    from app.services.routing.amap import walking_distance_from_raw

    cache = SqliteRouteCacheRepository(db_path)
    raw = copy.deepcopy(TRANSIT_OK)
    raw["route"]["transits"][0]["walking_distance"] = "820"
    old = parse_route("transit", raw)
    # 模拟板块 3 存的旧结果：没有 walkingDistanceMeters
    from app.schemas.route import RouteOut
    route = RouteOut(mode="transit", status="ok", durationMinutes=old.durationMinutes)
    entry = CachedRoute(route=route, origin="o", destination="d", checkedAt=NOW, expiresAt=NOW + timedelta(days=7))
    cache.put("a", "b", "transit", entry, "amap", raw)
    cache.put("a", "c", "walk", CachedRoute(route=RouteOut(mode="walk", status="ok", distanceMeters=500),
              origin="o", destination="d", checkedAt=NOW, expiresAt=NOW + timedelta(days=7)), "amap", WALK_OK)

    assert cache.fill_walking_distances(walking_distance_from_raw) == 2
    assert cache.get("a", "b", "transit").route.walkingDistanceMeters == 820  # type: ignore[union-attr]
    assert cache.get("a", "c", "walk").route.walkingDistanceMeters == 700  # type: ignore[union-attr]
    # 再跑一次没有要补的；有效期不变
    assert cache.fill_walking_distances(walking_distance_from_raw) == 0
    assert cache.get("a", "b", "transit").expiresAt == NOW + timedelta(days=7)  # type: ignore[union-attr]


async def test_ttl_per_mode(db_path: Path) -> None:
    svc = make_service(db_path, FakeProvider(), Clock(NOW))
    a, b = place("a", 114.3), place("b", 114.4)
    assert (await svc.route(a, b, "walk")).expiresAt == NOW + timedelta(days=30)
    assert (await svc.route(a, b, "transit")).expiresAt == NOW + timedelta(days=7)


async def test_expired_cache_used_when_amap_fails(db_path: Path) -> None:
    prov, clock = FakeProvider(), Clock(NOW)
    svc = make_service(db_path, prov, clock)
    a, b = place("a", 114.3), place("b", 114.4)
    await svc.route(a, b, "walk")
    clock.t = NOW + timedelta(days=31)
    prov.fail = RouteProviderError("amap-10003", "今天的高德调用次数用完了")
    r = await svc.route(a, b, "walk")
    assert r.status == "ok" and r.cache == "stale" and r.checkedAt == NOW
    assert r.warning and "次数用完" in r.warning


async def test_error_without_cache(db_path: Path) -> None:
    prov = FakeProvider()
    prov.fail = RouteProviderError("amap-key-missing", "没有 key")
    r = await make_service(db_path, prov, Clock(NOW)).route(place("a", 114.3), place("b", 114.4), "walk")
    assert r.status == "error" and r.error and r.error.code == "amap-key-missing"


async def test_moved_poi_invalidates_cache(db_path: Path) -> None:
    prov = FakeProvider()
    svc = make_service(db_path, prov, Clock(NOW))
    await svc.route(place("a", 114.3), place("b", 114.4), "walk")
    await svc.route(place("a", 114.31), place("b", 114.4), "walk")
    assert prov.calls == 2


# ---------- 接口 ----------

@pytest.fixture()
def client(db_path: Path):
    prov = FakeProvider()

    async def fake_provider():
        yield prov

    app.dependency_overrides[get_poi_repository] = lambda: SqlitePoiRepository(db_path)
    app.dependency_overrides[get_route_provider] = fake_provider
    app.dependency_overrides[get_route_cache] = lambda: SqliteRouteCacheRepository(db_path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_compare_endpoint(client: TestClient, db_path: Path) -> None:
    repo = SqlitePoiRepository(db_path)
    pois = repo.list_pois()
    assert len(pois) >= 2
    a, b = pois[0].id, pois[1].id
    res = client.get("/api/routes/compare", params={"from": a, "to": b})
    assert res.status_code == 200
    body = res.json()
    assert [r["mode"] for r in body["routes"]] == ["walk", "transit", "drive"]
    assert body["origin"]["id"] == a and all(r["status"] == "ok" for r in body["routes"])


def test_compare_unknown_and_same(client: TestClient, db_path: Path) -> None:
    a = SqlitePoiRepository(db_path).list_pois()[0].id
    assert client.get("/api/routes/compare", params={"from": a, "to": "nope"}).status_code == 404
    assert client.get("/api/routes/compare", params={"from": a, "to": a}).status_code == 400
