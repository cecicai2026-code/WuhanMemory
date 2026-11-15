"""两个景点之间怎么走：先看缓存，过期了再向路线 provider（现在是高德）查，查到的存回缓存。

- 只接受景点 id，不接受任意坐标：路线都挂在景点资料上，也避免接口被拿去随便查。
- 缓存多久过期（2026-11-15 Cecilia 选的方案 A）：步行 30 天，公交地铁 7 天，驾车 1 天。
  步行路基本不变；公交线路和班次会调整；驾车时间是查询那一刻的路况，变得最快。
- 过期后重查失败时，先返回旧结果并标 stale，界面上写"已过期"和核实时间，不直接报错。
- 公交地铁统一按当天上午 10 点出发查，避免半夜查到"地铁停运、没有方案"又被缓存一周。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol

from app.data_quality.rules import CITY_TZ
from app.repositories.poi_repository import PoiRepository
from app.repositories.route_cache_repository import CachedRoute, RouteCacheRepository
from app.schemas.poi import PoiFile
from app.schemas.route import (
    ROUTE_MODES,
    GeoPointOut,
    RouteCompareOut,
    RouteError,
    RouteMode,
    RouteOut,
    RoutePlace,
    RouteSource,
)
from app.services.routing.amap import ProviderRoute, RouteProviderError

ROUTE_TTL_DAYS: dict[RouteMode, int] = {"walk": 30, "transit": 7, "drive": 1}
TRANSIT_DEPART_HOUR = 10


class RouteProvider(Protocol):
    """路线 provider 的边界。换别家路线服务时实现这个方法。"""

    name: str

    async def plan(self, mode: RouteMode, origin: GeoPointOut, destination: GeoPointOut, depart_at: datetime) -> ProviderRoute: ...


class UnknownPoiError(Exception):
    pass


def now_in_city() -> datetime:
    return datetime.now(CITY_TZ)


def _place(poi: PoiFile) -> RoutePlace:
    if poi.location is None or poi.location.value is None:
        # 检查脚本保证导入的景点都有坐标，这里只是防御
        raise UnknownPoiError(f"景点 {poi.id} 没有坐标")
    loc = poi.location.value
    return RoutePlace(id=poi.id, name=poi.name, location=GeoPointOut(lng=loc.lng, lat=loc.lat))


def _coord(p: GeoPointOut) -> str:
    return f"{p.lng:.6f},{p.lat:.6f}"


class RouteService:
    def __init__(
        self,
        pois: PoiRepository,
        provider: RouteProvider,
        cache: RouteCacheRepository,
        now: Callable[[], datetime] = now_in_city,
    ) -> None:
        self.pois = pois
        self.provider = provider
        self.cache = cache
        self.now = now

    def places(self, from_id: str, to_id: str) -> tuple[RoutePlace, RoutePlace]:
        found = []
        for poi_id in (from_id, to_id):
            poi = self.pois.get_poi(poi_id)
            if poi is None:
                raise UnknownPoiError(f"没有这个景点：{poi_id}")
            found.append(_place(poi))
        return found[0], found[1]

    async def route(self, origin: RoutePlace, destination: RoutePlace, mode: RouteMode) -> RouteOut:
        now = self.now()
        o, d = _coord(origin.location), _coord(destination.location)
        cached = self.cache.get(origin.id, destination.id, mode)
        # 景点坐标改过的话，旧缓存不能用
        if cached and (cached.origin, cached.destination) != (o, d):
            cached = None
        if cached and cached.expiresAt > now:
            return cached.route.model_copy(update={"cache": "cached", "warning": None})

        depart = now.replace(hour=TRANSIT_DEPART_HOUR, minute=0, second=0, microsecond=0)
        try:
            found = await self.provider.plan(mode, origin.location, destination.location, depart)
        except RouteProviderError as exc:
            if cached:
                return cached.route.model_copy(
                    update={"cache": "stale", "warning": f"缓存已过期，重新查询失败：{exc.message}"}
                )
            return RouteOut(mode=mode, status="error", error=RouteError(code=exc.code, message=exc.message))

        expires = now + timedelta(days=ROUTE_TTL_DAYS[mode])
        route = RouteOut(
            mode=mode,
            status="ok" if found.status == "ok" else "none",
            durationMinutes=found.durationMinutes,
            distanceMeters=found.distanceMeters,
            cost=found.cost,
            summary=found.summary,
            reason=found.reason,
            polyline=found.polyline,
            source=RouteSource(provider="amap", api=found.api),
            checkedAt=now,
            expiresAt=expires,
        )
        self.cache.put(
            origin.id,
            destination.id,
            mode,
            CachedRoute(route=route, origin=o, destination=d, checkedAt=now, expiresAt=expires),
            self.provider.name,
            found.raw,
        )
        return route.model_copy(update={"cache": "fresh"})

    async def compare(self, from_id: str, to_id: str) -> RouteCompareOut:
        origin, destination = self.places(from_id, to_id)
        # 一个一个查，不并发：高德个人 key 的每秒请求数很低
        routes = [await self.route(origin, destination, mode) for mode in ROUTE_MODES]
        return RouteCompareOut(origin=origin, destination=destination, routes=routes)
