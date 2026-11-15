"""相邻两站之间用什么交通方式。由程序按规则定，时间用高德查到的真实时间，不用模型说的。

规则（2026-11-15 Cecilia 确认）：
1. 先查步行。步行在 15 分钟以内（用户说"尽量走路"时放宽到 30 分钟）就走过去。
2. 否则按交通偏好：地铁公交优先和尽量走路 → 公交地铁；打车 → 驾车（打车）。
3. 高德说没有公交方案（多半是两地太近）时改步行。
4. 查询出错时如实保留出错的结果，校验时给"交通查不到，无法校验"的警告。

板块 3 的 RouteService 先查 SQLite 缓存，没过期就不调用高德。
"""

from __future__ import annotations

from app.schemas.itinerary import ItineraryLeg
from app.schemas.planning import TransportPreference
from app.schemas.route import RouteMode, RouteOut
from app.services.routing.service import RouteService

WALK_MAX_MINUTES = 15
WALK_MAX_MINUTES_WALKER = 30

PREFERRED_MODE: dict[TransportPreference, RouteMode] = {"metro": "transit", "walk": "transit", "taxi": "drive"}
MODE_LABELS: dict[RouteMode, str] = {"walk": "步行", "transit": "公交地铁", "drive": "打车"}


def _ok(route: RouteOut) -> bool:
    return route.status == "ok" and route.durationMinutes is not None


async def choose_leg(
    service: RouteService,
    from_id: str,
    to_id: str,
    preference: TransportPreference,
    *,
    walk_max: int | None = None,
) -> ItineraryLeg:
    """walk_max：步行超过多少分钟就改坐车，不给就按上面的规则（板块 5B 的"轻松少走路"给 10 分钟）。"""
    origin, destination = service.places(from_id, to_id)
    if walk_max is not None:
        limit = walk_max
    else:
        limit = WALK_MAX_MINUTES_WALKER if preference == "walk" else WALK_MAX_MINUTES

    walk = await service.route(origin, destination, "walk")
    if _ok(walk) and walk.durationMinutes is not None and walk.durationMinutes <= limit:
        return ItineraryLeg(
            fromPoiId=from_id, toPoiId=to_id, route=walk, choice=f"步行 {walk.durationMinutes} 分钟，走过去"
        )

    mode = PREFERRED_MODE[preference]
    other = await service.route(origin, destination, mode)
    if _ok(other):
        return ItineraryLeg(fromPoiId=from_id, toPoiId=to_id, route=other, choice=f"步行超过 {limit} 分钟，{MODE_LABELS[mode]}")
    if other.status == "none" and _ok(walk):
        return ItineraryLeg(
            fromPoiId=from_id, toPoiId=to_id, route=walk, choice=f"高德没有{MODE_LABELS[mode]}方案，改步行"
        )
    reason = other.error.message if other.error else (other.reason or "没有方案")
    return ItineraryLeg(fromPoiId=from_id, toPoiId=to_id, route=other, choice=f"{MODE_LABELS[mode]}没查到：{reason}")
