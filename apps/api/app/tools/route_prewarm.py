"""路线预热：把开放景点两两之间的步行和公交地铁路线先查好存进缓存（板块 5B）。

一轮规划要排三份方案，三份用到的路线大多是同一批。先把它们查好，规划时几乎不用再问高德，也不会撞上高德的每秒次数限制。

用法（在项目根目录，需要 apps/api/.env 里的 AMAP_WEB_SERVICE_KEY）：
    corepack pnpm routes:prewarm            # 先补旧缓存的换乘步行距离，再查缺的路线
    corepack pnpm routes:prewarm --dry-run  # 只补旧缓存、数一数要查几条，不调用高德

做的事：
1. 旧缓存（板块 3、5 存的）没有"换乘步行距离"，从存着的高德原始返回里补，不发请求。
2. 暂停开放的景点不算。剩下的景点两两之间（A 到 B 和 B 到 A 分开算）查步行和公交地铁两种。
   缓存里已有、没过期的跳过；其余一个一个查（两次请求之间隔一下，和网站用同一个排队）。
不查打车：只有用户说打车时才用到，按需再查。key 不会打印。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import permutations

import httpx

from app.core.config import settings
from app.repositories.poi_repository import SqlitePoiRepository
from app.repositories.route_cache_repository import SqliteRouteCacheRepository
from app.schemas.route import RouteMode
from app.services.planning.candidates import is_closed
from app.services.routing.amap import AmapRouteProvider, walking_distance_from_raw
from app.services.routing.service import RouteService

PREWARM_MODES: tuple[RouteMode, ...] = ("walk", "transit")


@dataclass
class PrewarmResult:
    pairs: int = 0
    # 缓存里已有、没过期，没问高德
    skipped: int = 0
    # fresh / stale / error 的条数
    outcomes: Counter[str] = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)


async def prewarm(
    service: RouteService,
    poi_ids: Sequence[str],
    *,
    modes: Sequence[RouteMode] = PREWARM_MODES,
    dry_run: bool = False,
    progress: Callable[[str], None] | None = None,
) -> PrewarmResult:
    result = PrewarmResult()
    jobs = [(a, b, m) for a, b in permutations(poi_ids, 2) for m in modes]
    result.pairs = len(jobs)
    for i, (a, b, mode) in enumerate(jobs, start=1):
        origin, destination = service.places(a, b)
        if service.has_fresh_cache(origin, destination, mode):
            result.skipped += 1
            continue
        if dry_run:
            result.outcomes["would-query"] += 1
            continue
        route = await service.route(origin, destination, mode)
        status = "error" if route.status == "error" else (route.cache or "fresh")
        result.outcomes[status] += 1
        if route.status == "error" and route.error is not None:
            result.errors.append(f"{a} → {b}（{mode}）：{route.error.message}")
        if progress is not None:
            progress(f"[{i}/{len(jobs)}] {a} → {b} {mode}：{status}")
    return result


async def _main(dry_run: bool) -> int:
    db = settings.database_path
    cache = SqliteRouteCacheRepository(db)
    filled = cache.fill_walking_distances(walking_distance_from_raw)
    print(f"旧缓存补上换乘步行距离：{filled} 条（没有发请求）")

    pois = SqlitePoiRepository(db)
    open_ids = [p.id for p in pois.list_pois() if not is_closed(p)]
    closed = [p.name for p in pois.list_pois() if is_closed(p)]
    print(f"开放景点 {len(open_ids)} 个" + (f"，暂停开放不算：{'、'.join(closed)}" if closed else ""))

    if not dry_run and not settings.amap_web_service_key:
        print("apps/api/.env 里没有 AMAP_WEB_SERVICE_KEY，查不了路线。", file=sys.stderr)
        return 1
    async with httpx.AsyncClient() as client:
        service = RouteService(pois, AmapRouteProvider(settings.amap_web_service_key, settings.amap_base_url, client), cache)
        result = await prewarm(service, open_ids, dry_run=dry_run, progress=print)

    print(f"\n一共 {result.pairs} 条（{len(open_ids)} 个景点两两、{'和'.join(PREWARM_MODES)}），缓存里已有 {result.skipped} 条")
    if dry_run:
        print(f"要向高德查 {result.outcomes['would-query']} 条（这次没有查）")
        return 0
    print(f"新查到 {result.outcomes['fresh']} 条，用了过期缓存 {result.outcomes['stale']} 条，出错 {result.outcomes['error']} 条")
    for line in result.errors:
        print("  " + line)
    return 1 if result.errors else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把开放景点两两之间的步行和公交地铁路线查好存进缓存")
    parser.add_argument("--dry-run", action="store_true", help="只补旧缓存、数要查几条，不调用高德")
    # pnpm 有的版本会把命令里的 -- 原样传进来
    args = parser.parse_args([a for a in (sys.argv[1:] if argv is None else argv) if a != "--"])
    return asyncio.run(_main(args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
