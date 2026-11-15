"""两个景点之间怎么走：先看缓存，过期了再向路线 provider（现在是高德）查，查到的存回缓存。

- 只接受景点 id，不接受任意坐标：路线都挂在景点资料上，也避免接口被拿去随便查。
- 缓存多久过期（2026-11-15 Cecilia 选的方案 A）：步行 30 天，公交地铁 7 天，驾车 1 天。
  步行路基本不变；公交线路和班次会调整；驾车时间是查询那一刻的路况，变得最快。
- 过期后重查失败时，先返回旧结果并标 stale，界面上写"已过期"和核实时间，不直接报错。
- 公交地铁统一按当天上午 10 点出发查，避免半夜查到"地铁停运、没有方案"又被缓存一周。
"""

from __future__ import annotations

import re
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
from app.core.lang import current_lang

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

    def has_fresh_cache(self, origin: RoutePlace, destination: RoutePlace, mode: RouteMode) -> bool:
        """缓存里有这条路线、坐标没变、还没过期：route() 不会去问高德。"""
        cached = self.cache.get(origin.id, destination.id, mode)
        if cached is None:
            return False
        same = (cached.origin, cached.destination) == (_coord(origin.location), _coord(destination.location))
        return same and cached.expiresAt > self.now()

    def cached_route(self, origin: RoutePlace, destination: RoutePlace, mode: RouteMode) -> RouteOut | None:
        """只读缓存：有没过期、坐标没变的结果就返回，否则返回 None。不调用高德（板块 6B：排行程前给模型看的交通表用）。"""
        if not self.has_fresh_cache(origin, destination, mode):
            return None
        cached = self.cache.get(origin.id, destination.id, mode)
        assert cached is not None
        return cached.route.model_copy(update={"cache": "cached", "warning": None})

    async def route(self, origin: RoutePlace, destination: RoutePlace, mode: RouteMode) -> RouteOut:
        # 缓存里存的是中文（高德给的线路名和程序写的说明）；英文版在取出来时换成英文（中英双语）
        return localize_route(await self._route(origin, destination, mode))

    async def _route(self, origin: RoutePlace, destination: RoutePlace, mode: RouteMode) -> RouteOut:
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
            walkingDistanceMeters=found.walkingDistanceMeters,
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


# ---------- 英文版（中英双语） ----------

# 程序自己写的、会存进缓存的固定说法（app/services/routing/amap.py）
_FIXED_EN = {
    "步行不花钱": "Walking is free",
    "高德估算的打车费": "Taxi fare estimated by AMap",
    "高德没有给出打车费": "AMap gave no taxi fare",
    "高德估算的票价": "Fare estimated by AMap",
    "高德没有给出票价": "AMap gave no fare",
    "高德没有给出公交地铁方案，可能是两地太近，建议步行。": "AMap found no bus or metro option; the two places may be too close, so walking is suggested.",
    "高德没有给出路线。": "AMap found no route.",
    "高德 Web 服务 key 不正确或已过期（apps/api/.env 的 AMAP_WEB_SERVICE_KEY）": "The AMap web service key is wrong or expired (AMAP_WEB_SERVICE_KEY in apps/api/.env)",
    "今天的高德调用次数用完了，明天 0 点自动恢复": "Today's AMap call quota is used up; it resets at midnight",
    "这个 key 不是 Web 服务类型，可能把 JS key 填成了 Web 服务 key": "This key isn't a web service key; the JS key may have been entered as the web service key",
    "请求太快，被高德限流了，稍后再试": "Requests were too fast and AMap rate-limited them; try again later",
}
_TOLLS = re.compile(r"；自己开车过路费约 ([\d.]+) 元")
_METRO = re.compile(r"^(?:轨道交通|地铁)(\d+)号线$")
_BUS = re.compile(r"^([0-9A-Za-z]+)路$")


def _fixed(text: str | None) -> str | None:
    if text is None:
        return None
    base = _TOLLS.sub(lambda m: f"; tolls about ¥{m.group(1)} if you drive yourself", text)
    head = text.split("；")[0] if "；" in text else text
    if head in _FIXED_EN:
        base = base.replace(head, _FIXED_EN[head], 1)
    if base.startswith("缓存已过期，重新查询失败："):
        base = "Cache expired and the new lookup failed: " + (_fixed(base[len("缓存已过期，重新查询失败："):]) or "")
    if base.startswith("高德返回错误："):
        base = "AMap returned an error: " + base[len("高德返回错误："):]
    return base


def _line(name: str) -> str:
    if m := _METRO.match(name):
        return f"Metro Line {m.group(1)}"
    if m := _BUS.match(name):
        return f"Bus {m.group(1)}"
    return name


def localize_route(route: RouteOut) -> RouteOut:
    """当前语言是英文时，把线路名（"轨道交通2号线" → "Metro Line 2"、"14路" → "Bus 14"）和程序写的固定说法换成英文。
    高德给的其他名字（例如有轨电车的线路名）保持原样。"""
    if current_lang() != "en":
        return route
    update: dict[str, object] = {
        "summary": " → ".join(_line(n) for n in route.summary.split(" → ")) if route.summary else route.summary,
        "reason": _fixed(route.reason),
        "warning": _fixed(route.warning),
    }
    if route.cost is not None:
        update["cost"] = route.cost.model_copy(update={"note": _fixed(route.cost.note)})
    if route.error is not None:
        update["error"] = route.error.model_copy(update={"message": _fixed(route.error.message)})
    return route.model_copy(update=update)

