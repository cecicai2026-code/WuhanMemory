"""路线接口返回的数据结构。前端类型在 packages/shared/src/route.ts，两边要一致。

字段说明见 docs/architecture/api-contracts.md 的"路线"一节。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

RouteMode = Literal["walk", "transit", "drive"]
ROUTE_MODES: tuple[RouteMode, ...] = ("walk", "transit", "drive")


class GeoPointOut(BaseModel):
    lng: float
    lat: float


class RouteCost(BaseModel):
    # free：步行不花钱；fare：公交地铁票价；taxi：打车费
    kind: Literal["free", "fare", "taxi"]
    amountCny: float | None
    note: str


class RouteSource(BaseModel):
    provider: Literal["amap"]
    api: str


class RouteError(BaseModel):
    code: str
    message: str


class RouteOut(BaseModel):
    mode: RouteMode
    # ok：有方案；none：高德没给方案（例如两点太近没有公交）；error：没查成
    status: Literal["ok", "none", "error"]
    durationMinutes: int | None = None
    distanceMeters: int | None = None
    cost: RouteCost | None = None
    # 公交地铁坐哪几条线，例如"地铁2号线 → 地铁4号线"
    summary: str | None = None
    # 高德没给方案时的说明
    reason: str | None = None
    polyline: list[GeoPointOut] = []
    source: RouteSource | None = None
    checkedAt: datetime | None = None
    expiresAt: datetime | None = None
    # fresh：刚向高德查的；cached：缓存里还没过期；stale：缓存过期了，重查又失败，先用旧的
    cache: Literal["fresh", "cached", "stale"] | None = None
    # stale 时说明为什么没更新
    warning: str | None = None
    error: RouteError | None = None


class RoutePlace(BaseModel):
    id: str
    name: str
    location: GeoPointOut


class RouteCompareOut(BaseModel):
    origin: RoutePlace
    destination: RoutePlace
    routes: list[RouteOut]
