"""相邻两站之间用什么交通方式。由程序按规则定，时间用高德查到的真实时间，不用模型说的。

规则（2026-11-15 Cecilia 确认）：
1. 先查步行。步行在 15 分钟以内（用户说"尽量走路"时放宽到 30 分钟）就走过去。
2. 否则按交通偏好：地铁公交优先和尽量走路 → 公交地铁；打车 → 驾车（打车）。
3. 高德说没有公交方案（多半是两地太近）时改步行。
4. 查询出错时如实保留出错的结果，校验时给"交通查不到，无法校验"的警告。

板块 3 的 RouteService 先查 SQLite 缓存，没过期就不调用高德。

板块 6B：排行程前给模型一张"真实交通表"（transit_table），每两站写程序会选的方式和分钟数。
表和校验用同一个判断（decide_leg），所以模型看到的时间就是校验时核对的时间。表只读缓存，不调用高德；
缓存里没有的两站照旧写直线距离，并注明没查到真实时间。
"""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.itinerary import ItineraryLeg
from app.schemas.planning import TransportPreference
from app.schemas.poi import PoiFile
from app.schemas.route import RouteMode, RouteOut
from app.core.lang import L
from app.services.planning.candidates import distance_km
from app.services.routing.service import RouteService

WALK_MAX_MINUTES = 15
WALK_MAX_MINUTES_WALKER = 30

PREFERRED_MODE: dict[TransportPreference, RouteMode] = {"metro": "transit", "walk": "transit", "taxi": "drive"}
MODE_LABELS: dict[RouteMode, str] = {"walk": "步行", "transit": "公交地铁", "drive": "打车"}
# leg.choice 写给人看，按当前语言写（MODE_LABELS 还用在给模型的交通表里，保持中文）
MODE_EN: dict[RouteMode, str] = {"walk": "walk", "transit": "bus/metro", "drive": "taxi"}


def _ok(route: RouteOut) -> bool:
    return route.status == "ok" and route.durationMinutes is not None


def walk_limit_minutes(preference: TransportPreference, walk_max: int | None) -> int:
    """步行超过多少分钟就改坐车。walk_max 是侧重给的（"轻松少走路"10 分钟），不给就按偏好。"""
    if walk_max is not None:
        return walk_max
    return WALK_MAX_MINUTES_WALKER if preference == "walk" else WALK_MAX_MINUTES


def decide_leg(
    from_id: str,
    to_id: str,
    walk: RouteOut,
    other: RouteOut | None,
    preference: TransportPreference,
    limit: int,
) -> ItineraryLeg | None:
    """按规则选方式。步行够近就走；否则要看 other（偏好的那种方式）。other 还没查时返回 None。"""
    if _ok(walk) and walk.durationMinutes is not None and walk.durationMinutes <= limit:
        return ItineraryLeg(
            fromPoiId=from_id, toPoiId=to_id, route=walk,
            choice=L(f"步行 {walk.durationMinutes} 分钟，走过去", f"{walk.durationMinutes} min on foot, so walk"),
        )
    if other is None:
        return None
    mode = PREFERRED_MODE[preference]
    if _ok(other):
        return ItineraryLeg(
            fromPoiId=from_id, toPoiId=to_id, route=other,
            choice=L(f"步行超过 {limit} 分钟，{MODE_LABELS[mode]}", f"over {limit} min on foot, so {MODE_EN[mode]}"),
        )
    if other.status == "none" and _ok(walk):
        return ItineraryLeg(
            fromPoiId=from_id, toPoiId=to_id, route=walk,
            choice=L(f"高德没有{MODE_LABELS[mode]}方案，改步行", f"AMap has no {MODE_EN[mode]} option, so walk"),
        )
    reason = other.error.message if other.error else (other.reason or L("没有方案", "no option"))
    return ItineraryLeg(
        fromPoiId=from_id, toPoiId=to_id, route=other,
        choice=L(f"{MODE_LABELS[mode]}没查到：{reason}", f"no {MODE_EN[mode]} route found: {reason}"),
    )


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
    limit = walk_limit_minutes(preference, walk_max)
    walk = await service.route(origin, destination, "walk")
    leg = decide_leg(from_id, to_id, walk, None, preference, limit)
    if leg is not None:
        return leg
    other = await service.route(origin, destination, PREFERRED_MODE[preference])
    leg = decide_leg(from_id, to_id, walk, other, preference, limit)
    assert leg is not None
    return leg


def cached_leg(
    service: RouteService,
    from_id: str,
    to_id: str,
    preference: TransportPreference,
    *,
    walk_max: int | None = None,
) -> ItineraryLeg | None:
    """和 choose_leg 一样的选法，但只读缓存。缓存里缺了要用的那一条，或者选出来的那段没有时间，返回 None。"""
    origin, destination = service.places(from_id, to_id)
    limit = walk_limit_minutes(preference, walk_max)
    walk = service.cached_route(origin, destination, "walk")
    if walk is None:
        return None
    leg = decide_leg(from_id, to_id, walk, None, preference, limit)
    if leg is None:
        other = service.cached_route(origin, destination, PREFERRED_MODE[preference])
        if other is None:
            return None
        leg = decide_leg(from_id, to_id, walk, other, preference, limit)
    if leg is None or not _ok(leg.route):
        return None
    return leg


def _leg_text(leg: ItineraryLeg) -> str:
    return f"{MODE_LABELS[leg.route.mode]} {leg.route.durationMinutes} 分钟"


def transit_table(
    service: RouteService,
    pois: Sequence[PoiFile],
    preference: TransportPreference,
    *,
    walk_max: int | None = None,
) -> list[str]:
    """候选两两之间、程序会选的交通方式和真实分钟数。来回一样的合成一行，例如 "a↔b 公交地铁 34 分钟"；
    不一样的写 "a→b 公交地铁 34 分钟，b→a 公交地铁 38 分钟"；缓存里没有的写直线距离。不调用高德。"""
    rows: list[str] = []
    items = list(pois)
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            there = cached_leg(service, a.id, b.id, preference, walk_max=walk_max)
            back = cached_leg(service, b.id, a.id, preference, walk_max=walk_max)
            if there is not None and back is not None:
                t, k = _leg_text(there), _leg_text(back)
                rows.append(f"{a.id}↔{b.id} {t}" if t == k else f"{a.id}→{b.id} {t}，{b.id}→{a.id} {k}")
            elif there is not None or back is not None:
                known = there or back
                assert known is not None
                rows.append(
                    f"{known.fromPoiId}→{known.toPoiId} {_leg_text(known)}，{known.toPoiId}→{known.fromPoiId} 没查到真实时间"
                )
            else:
                rows.append(f"{a.id}—{b.id} 没查到真实时间，直线 {distance_km(a, b):.1f}km")
    return rows
