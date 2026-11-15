"""排行程前给模型看的真实交通表（板块 6B）。用假高德和临时 SQLite，不联网；景点是虚构的测试景点。

要点：表里每两站的方式和分钟数，和校验时 choose_leg 选的一样；只读缓存，不调用高德；缓存里没有的写直线距离。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.data_quality.rules import CITY_TZ
from app.repositories.route_cache_repository import SqliteRouteCacheRepository
from app.services.planning.transport import cached_leg, choose_leg, transit_table
from app.services.routing.service import RouteService
from tests.test_planning_pipeline import FakeRouteProvider, MemoryPois, poi

POIS = [poi("a"), poi("b"), poi("c")]


def service(tmp_path: Path, table: dict[tuple[str, str, str], Any], *, now: datetime | None = None) -> tuple[RouteService, FakeRouteProvider]:
    provider = FakeRouteProvider(table)
    clock = now or datetime(2026, 11, 15, 12, 0, tzinfo=CITY_TZ)
    return RouteService(MemoryPois(POIS), provider, SqliteRouteCacheRepository(tmp_path / "t.db"), now=lambda: clock), provider


async def warm(s: RouteService, pairs: list[tuple[str, str]], preference: str = "metro", walk_max: int | None = None) -> None:
    """像真实规划那样走一遍 choose_leg，把要用的路线放进缓存。"""
    for a, b in pairs:
        await choose_leg(s, a, b, preference, walk_max=walk_max)  # type: ignore[arg-type]


ALL_PAIRS = [("a", "b"), ("b", "a"), ("a", "c"), ("c", "a"), ("b", "c"), ("c", "b")]


async def test_table_matches_what_validation_uses(tmp_path: Path) -> None:
    table = {("a", "b", "walk"): 9, ("b", "a", "walk"): 9, ("a", "c", "walk"): 40, ("a", "c", "transit"): 34,
             ("c", "a", "walk"): 40, ("c", "a", "transit"): 38, ("b", "c", "walk"): 50, ("b", "c", "transit"): 25,
             ("c", "b", "walk"): 50, ("c", "b", "transit"): 25}
    s, provider = service(tmp_path, table)
    await warm(s, ALL_PAIRS)
    before = len(provider.calls)

    rows = transit_table(s, [p for p in s.pois.list_pois()], "metro")
    # 走得到的写步行，远的写公交地铁；来回一样的合成一行，不一样的分开写
    assert rows == ["a↔b 步行 9 分钟", "a→c 公交地铁 34 分钟，c→a 公交地铁 38 分钟", "b↔c 公交地铁 25 分钟"]
    # 只读缓存，没有调用高德
    assert len(provider.calls) == before
    # 和校验时选的一样
    for a, b in ALL_PAIRS:
        real = await choose_leg(s, a, b, "metro")
        cached = cached_leg(s, a, b, "metro")
        assert cached is not None and (cached.route.mode, cached.route.durationMinutes) == (real.route.mode, real.route.durationMinutes)


async def test_relaxed_walk_limit_changes_the_mode(tmp_path: Path) -> None:
    # 走 12 分钟：默认（15 分钟以内）走过去；"轻松少走路"（10 分钟以内）改坐地铁
    table = {("a", "b", "walk"): 12, ("b", "a", "walk"): 12, ("a", "b", "transit"): 20, ("b", "a", "transit"): 20}
    s, _ = service(tmp_path, table)
    await warm(s, [("a", "b"), ("b", "a")])
    await warm(s, [("a", "b"), ("b", "a")], walk_max=10)
    pois = [p for p in s.pois.list_pois() if p.id in ("a", "b")]
    assert transit_table(s, pois, "metro") == ["a↔b 步行 12 分钟"]
    assert transit_table(s, pois, "metro", walk_max=10) == ["a↔b 公交地铁 20 分钟"]


async def test_missing_cache_falls_back_to_straight_line_without_calling_amap(tmp_path: Path) -> None:
    s, provider = service(tmp_path, {})
    rows = transit_table(s, [p for p in s.pois.list_pois()], "taxi")
    assert all("没查到真实时间，直线" in r and r.endswith("km") for r in rows) and len(rows) == 3
    assert provider.calls == []


async def test_walk_cached_but_preferred_mode_missing(tmp_path: Path) -> None:
    # 打车的用户：步行有缓存（太远，走不过去），驾车没有缓存 → 不知道，写直线距离
    s, provider = service(tmp_path, {("a", "b", "walk"): 60, ("b", "a", "walk"): 60})
    origin, dest = s.places("a", "b")
    await s.route(origin, dest, "walk")
    origin, dest = s.places("b", "a")
    await s.route(origin, dest, "walk")
    pois = [p for p in s.pois.list_pois() if p.id in ("a", "b")]
    assert transit_table(s, pois, "taxi")[0].startswith("a—b 没查到真实时间，直线")
    assert len(provider.calls) == 2


async def test_one_direction_known(tmp_path: Path) -> None:
    s, _ = service(tmp_path, {("a", "b", "walk"): 9})
    await warm(s, [("a", "b")])
    pois = [p for p in s.pois.list_pois() if p.id in ("a", "b")]
    assert transit_table(s, pois, "metro") == ["a→b 步行 9 分钟，b→a 没查到真实时间"]


async def test_no_transit_plan_means_walk(tmp_path: Path) -> None:
    # 高德说没有公交方案（两地太近）：校验时改步行，表里也写步行
    table = {("a", "b", "walk"): 18, ("a", "b", "transit"): "none"}
    s, _ = service(tmp_path, table)
    await warm(s, [("a", "b")])
    leg = cached_leg(s, "a", "b", "metro")
    assert leg is not None and leg.route.mode == "walk" and leg.route.durationMinutes == 18


async def test_expired_cache_is_not_used(tmp_path: Path) -> None:
    s, _ = service(tmp_path, {("a", "b", "walk"): 9})
    await warm(s, [("a", "b")])
    later, _ = service(tmp_path, {}, now=datetime(2027, 3, 1, 12, 0, tzinfo=CITY_TZ))  # 步行缓存 30 天，早过期了
    assert cached_leg(later, "a", "b", "metro") is None


async def test_failed_lookup_is_not_shown_as_a_time(tmp_path: Path) -> None:
    # 公交地铁查询出错：出错的结果不进缓存，表里不当成时间
    table = {("a", "b", "walk"): 40, ("a", "b", "transit"): "error"}
    s, _ = service(tmp_path, table)
    await warm(s, [("a", "b")])
    assert cached_leg(s, "a", "b", "metro") is None
