"""路线预热脚本的测试。不联网：用假的高德返回（tests/test_routing.py 里的虚构数据）。"""

from __future__ import annotations

from pathlib import Path

from app.repositories.poi_repository import SqlitePoiRepository
from app.repositories.route_cache_repository import SqliteRouteCacheRepository
from app.services.routing.service import RouteService
from app.tools.route_prewarm import prewarm
from tests.test_routing import NOW, Clock, FakeProvider, db_path  # noqa: F401  (db_path 是 fixture)


def _ids(db: Path) -> list[str]:
    ids = [p.id for p in SqlitePoiRepository(db).list_pois()]
    assert len(ids) >= 2
    return ids


async def test_queries_every_ordered_pair_once_then_uses_cache(db_path: Path) -> None:  # noqa: F811
    prov = FakeProvider()
    svc = RouteService(SqlitePoiRepository(db_path), prov, SqliteRouteCacheRepository(db_path), Clock(NOW))
    ids = _ids(db_path)
    first = await prewarm(svc, ids)
    # n 个景点两两（分方向）n×(n-1) 对 × 步行、公交 2 种
    n = len(ids) * (len(ids) - 1) * 2
    assert first.pairs == n and prov.calls == n
    assert first.outcomes["fresh"] == n and first.skipped == 0
    second = await prewarm(svc, ids)
    assert prov.calls == n and second.skipped == n


async def test_dry_run_does_not_call_amap(db_path: Path) -> None:  # noqa: F811
    prov = FakeProvider()
    svc = RouteService(SqlitePoiRepository(db_path), prov, SqliteRouteCacheRepository(db_path), Clock(NOW))
    ids = _ids(db_path)
    result = await prewarm(svc, ids, dry_run=True)
    assert prov.calls == 0 and result.outcomes["would-query"] == len(ids) * (len(ids) - 1) * 2


async def test_errors_are_listed(db_path: Path) -> None:  # noqa: F811
    from app.services.routing.amap import RouteProviderError

    prov = FakeProvider()
    prov.fail = RouteProviderError("amap-10003", "今天的高德调用次数用完了")
    svc = RouteService(SqlitePoiRepository(db_path), prov, SqliteRouteCacheRepository(db_path), Clock(NOW))
    result = await prewarm(svc, _ids(db_path)[:2], modes=("walk",))
    assert result.outcomes["error"] == 2
    assert "调用次数用完" in result.errors[0]
