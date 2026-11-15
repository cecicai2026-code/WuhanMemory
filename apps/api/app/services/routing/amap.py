"""高德路径规划 2.0（Web 服务 API）。只在后端调用，key 是 AMAP_WEB_SERVICE_KEY。

文档：https://lbs.amap.com/api/webservice/guide/api/newroute
- 步行 /v5/direction/walking，驾车 /v5/direction/driving，公交地铁 /v5/direction/transit/integrated
- show_fields=cost,polyline 才返回时间、费用和折线
- 坐标 GCJ-02，经纬度不超过 6 位小数
- 公交要 city1、city2（citycode，武汉是 027）；date、time 指定出发时间（time 的格式是 9-54）

官方文档没写清公交折线的结构（只说"参考 v3 老接口"），所以折线解析写得宽一些：
字符串和 {"polyline": "..."} 两种都认。高德的原始返回会存进路线缓存表，方便核对。
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from app.schemas.route import GeoPointOut, RouteCost, RouteMode

WUHAN_CITYCODE = "027"
TIMEOUT_SECONDS = 10.0
# 个人开发者的每秒请求数很低（板块 2 查坐标时碰到过），两次请求之间至少隔这么久
REQUEST_GAP_SECONDS = 0.4
QPS_RETRY_SECONDS = 1.5

PATHS: dict[RouteMode, str] = {
    "walk": "/v5/direction/walking",
    "transit": "/v5/direction/transit/integrated",
    "drive": "/v5/direction/driving",
}

# 高德错误码（https://lbs.amap.com/api/webservice/guide/tools/info）→ 给人看的说明
INFOCODE_TEXT = {
    "10001": "高德 Web 服务 key 不正确或已过期（apps/api/.env 的 AMAP_WEB_SERVICE_KEY）",
    "10003": "今天的高德调用次数用完了，明天 0 点自动恢复",
    "10009": "这个 key 不是 Web 服务类型，可能把 JS key 填成了 Web 服务 key",
    "10021": "请求太快，被高德限流了，稍后再试",
}
QPS_CODE = "10021"


class RouteProviderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ProviderRoute:
    status: str  # "ok" 或 "none"
    api: str
    raw: dict[str, Any]
    durationMinutes: int | None = None
    distanceMeters: int | None = None
    walkingDistanceMeters: int | None = None
    cost: RouteCost | None = None
    summary: str | None = None
    reason: str | None = None
    polyline: list[GeoPointOut] = field(default_factory=list)


def _num(v: Any) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v.strip():
        try:
            return float(v)
        except ValueError:
            return None
    return None


def _minutes(seconds: Any) -> int | None:
    s = _num(seconds)
    return None if s is None else max(1, round(s / 60))


def _int(v: Any) -> int | None:
    n = _num(v)
    return None if n is None else round(n)


def parse_points(text: str) -> list[GeoPointOut]:
    """"lng,lat;lng,lat" → 点列表。坏掉的点跳过。"""
    out: list[GeoPointOut] = []
    for pair in text.split(";"):
        parts = pair.split(",")
        if len(parts) != 2:
            continue
        lng, lat = _num(parts[0]), _num(parts[1])
        if lng is not None and lat is not None:
            out.append(GeoPointOut(lng=lng, lat=lat))
    return out


def collect_polyline(node: Any) -> list[GeoPointOut]:
    """按文档顺序收集 node 里所有的 polyline。公交一段里有好几条可选线路（buslines）时只取第一条。"""
    out: list[GeoPointOut] = []
    if isinstance(node, list):
        for item in node:
            out.extend(collect_polyline(item))
    elif isinstance(node, dict):
        for key, value in node.items():
            if key == "polyline":
                if isinstance(value, str):
                    out.extend(parse_points(value))
                elif isinstance(value, dict) and isinstance(value.get("polyline"), str):
                    out.extend(parse_points(value["polyline"]))
            elif key == "buslines" and isinstance(value, list):
                out.extend(collect_polyline(value[:1]))
            else:
                out.extend(collect_polyline(value))
    return out


_PAREN = re.compile(r"[（(].*?[)）]")


def _line_name(name: str) -> str:
    # "地铁2号线(天河机场--佛祖岭)" → "地铁2号线"
    return _PAREN.sub("", name).strip()


def transit_summary(segments: list[Any]) -> str | None:
    names: list[str] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        bus = seg.get("bus")
        if isinstance(bus, dict):
            lines = bus.get("buslines")
            if isinstance(lines, list) and lines and isinstance(lines[0], dict) and isinstance(lines[0].get("name"), str):
                names.append(_line_name(lines[0]["name"]))
        railway = seg.get("railway")
        if isinstance(railway, dict) and isinstance(railway.get("name"), str) and railway["name"]:
            names.append(_line_name(railway["name"]))
    return " → ".join(names) if names else None


def transit_walking_distance(plan: dict[str, Any]) -> int | None:
    """公交地铁方案里要走的路（米）：换乘和进出站。先用高德给的 walking_distance，没有就把每段的步行距离加起来。"""
    total = _int(plan.get("walking_distance"))
    if total is not None:
        return total
    parts = [_int((seg.get("walking") or {}).get("distance")) for seg in plan.get("segments") or [] if isinstance(seg, dict)]
    known = [p for p in parts if p is not None]
    return sum(known) if known else None


def walking_distance_from_raw(mode: RouteMode, payload: dict[str, Any]) -> int | None:
    """从高德的原始返回里读出要走的路。给旧缓存补字段用，不发请求。"""
    route = payload.get("route") or {}
    if mode == "transit":
        plans = route.get("transits") or []
        return transit_walking_distance(plans[0]) if plans else None
    paths = route.get("paths") or []
    if not paths:
        return None
    return _int(paths[0].get("distance")) if mode == "walk" else 0


def parse_route(mode: RouteMode, payload: dict[str, Any]) -> ProviderRoute:
    api = PATHS[mode]
    if payload.get("status") != "1":
        code = str(payload.get("infocode", ""))
        info = payload.get("info", "未知错误")
        raise RouteProviderError(f"amap-{code or 'error'}", INFOCODE_TEXT.get(code, f"高德返回错误：{info}（{code}）"))
    route = payload.get("route") or {}

    if mode == "transit":
        plans = route.get("transits") or []
        if not plans:
            return ProviderRoute(status="none", api=api, raw=payload, reason="高德没有给出公交地铁方案，可能是两地太近，建议步行。")
        plan = plans[0]
        cost = plan.get("cost") or {}
        fare = _num(cost.get("transit_fee"))
        segments = plan.get("segments") or []
        return ProviderRoute(
            status="ok",
            api=api,
            raw=payload,
            durationMinutes=_minutes(cost.get("duration")),
            distanceMeters=_int(plan.get("distance")),
            walkingDistanceMeters=transit_walking_distance(plan),
            cost=RouteCost(kind="fare", amountCny=fare, note="高德估算的票价" if fare is not None else "高德没有给出票价"),
            summary=transit_summary(segments),
            polyline=collect_polyline(segments),
        )

    paths = route.get("paths") or []
    if not paths:
        return ProviderRoute(status="none", api=api, raw=payload, reason="高德没有给出路线。")
    path = paths[0]
    cost = path.get("cost") or {}
    result = ProviderRoute(
        status="ok",
        api=api,
        raw=payload,
        durationMinutes=_minutes(cost.get("duration", path.get("duration"))),
        distanceMeters=_int(path.get("distance")),
        walkingDistanceMeters=_int(path.get("distance")) if mode == "walk" else 0,
        polyline=collect_polyline(path.get("steps") or []),
    )
    if mode == "walk":
        result.cost = RouteCost(kind="free", amountCny=0, note="步行不花钱")
    else:
        taxi = _num(route.get("taxi_cost"))
        tolls = _num(cost.get("tolls"))
        note = "高德估算的打车费" if taxi is not None else "高德没有给出打车费"
        if tolls:
            note += f"；自己开车过路费约 {tolls:g} 元"
        result.cost = RouteCost(kind="taxi", amountCny=taxi, note=note)
    return result


class _Throttle:
    """所有路线请求共用：两次请求之间至少隔 REQUEST_GAP_SECONDS。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self, gap: float) -> None:
        async with self._lock:
            delay = self._last + gap - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


_throttle = _Throttle()


class AmapRouteProvider:
    name = "amap"

    def __init__(
        self,
        key: str | None,
        base_url: str,
        client: httpx.AsyncClient,
        *,
        gap_seconds: float = REQUEST_GAP_SECONDS,
        retry_seconds: float = QPS_RETRY_SECONDS,
    ) -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")
        self.client = client
        self.gap_seconds = gap_seconds
        self.retry_seconds = retry_seconds

    @staticmethod
    def coord(p: GeoPointOut) -> str:
        return f"{p.lng:.6f},{p.lat:.6f}"

    async def plan(self, mode: RouteMode, origin: GeoPointOut, destination: GeoPointOut, depart_at: datetime) -> ProviderRoute:
        if not self.key:
            raise RouteProviderError("amap-key-missing", "后端没有配置高德 Web 服务 key（apps/api/.env 的 AMAP_WEB_SERVICE_KEY）")
        params = {
            "key": self.key,
            "origin": self.coord(origin),
            "destination": self.coord(destination),
            "show_fields": "cost,polyline",
        }
        if mode == "transit":
            params.update(
                city1=WUHAN_CITYCODE,
                city2=WUHAN_CITYCODE,
                date=depart_at.strftime("%Y-%m-%d"),
                time=f"{depart_at.hour}-{depart_at.minute:02d}",
            )
        for attempt in range(2):
            await _throttle.wait(self.gap_seconds)
            try:
                res = await self.client.get(self.base_url + PATHS[mode], params=params, timeout=TIMEOUT_SECONDS)
                res.raise_for_status()
                payload = res.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise RouteProviderError("amap-unreachable", f"连不上高德服务器：{type(exc).__name__}") from exc
            if payload.get("status") != "1" and str(payload.get("infocode")) == QPS_CODE and attempt == 0:
                await asyncio.sleep(self.retry_seconds)
                continue
            return parse_route(mode, payload)
        raise RouteProviderError("amap-10021", INFOCODE_TEXT[QPS_CODE])  # 不会走到这里
