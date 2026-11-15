"""景点接口返回的数据结构（GET /api/pois、GET /api/pois/{id}）。

和 data/pois/*.json 的区别：
- 每条信息多了 status（按今天的日期算出来的），和展开后的 source；
- 照片多了 url；
- 列表只返回概要。
"""

from __future__ import annotations

from datetime import date
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

from app.schemas.poi import (
    Coordinates,
    FoodItem,
    OpeningHours,
    OperatingStatus,
    Payment,
    PhotoLicense,
    PhotoSpot,
    Reservation,
    Review,
    SourceType,
    Ticket,
    Transport,
    Verification,
)

# 一条信息在界面上的状态
#   verified  实地核实或核对过来源，没过期 → "已核实"
#   pending   官网占位，待 Cecilia 确认 → "待确认"
#   expired   过了 expiresAt → "已过期"（不管原来是怎么核实的）
#   missing   TODO，没有资料 → "待补充"
FactStatus = Literal["verified", "pending", "expired", "missing"]
# 整个景点的状态：有一条过期就是 expired，有一条待确认或待补充就是 pending
PoiStatus = Literal["verified", "pending", "expired"]

T = TypeVar("T")


class SourceOut(BaseModel):
    id: str
    type: SourceType
    title: str
    url: str | None
    accessedAt: date | None


class FactOut(BaseModel, Generic[T]):
    value: T | None
    verification: Verification
    status: FactStatus
    source: SourceOut | None
    # 同一条信息还参考的其他来源
    extraSources: list[SourceOut] = []
    lastCheckedAt: date | None
    expiresAt: date | None
    todo: str | None
    note: str | None


class PhotoOut(BaseModel):
    file: str
    caption: str
    license: PhotoLicense
    placeholder: bool
    author: str | None
    takenAt: date | None
    sourceUrl: str | None
    retrievedAt: date | None
    licenseNote: str | None
    # 相对于后端地址，例如 /media/photos/<id>/a.jpg；占位照片不在本机时为 null
    url: str | None
    # 800 宽的缩略图（板块 1B），列表、图册、立体场景用它；没有 url 时也是 null
    thumbUrl: str | None = None


class FactCounts(BaseModel):
    verified: int = 0
    pending: int = 0
    expired: int = 0
    missing: int = 0


class PoiSummaryOut(BaseModel):
    id: str
    name: str
    district: str
    category: str
    tags: list[str]
    location: Coordinates
    status: PoiStatus
    counts: FactCounts
    coverPhoto: PhotoOut | None
    # 开放状态；资料里没写（正常开放）时为 null
    operatingStatus: FactOut[OperatingStatus] | None = None


class PoiDetailOut(PoiSummaryOut):
    sources: list[SourceOut]
    address: FactOut[str]
    intro: FactOut[str]
    history: FactOut[str]
    openingHours: FactOut[OpeningHours]
    ticket: FactOut[Ticket]
    reservation: FactOut[Reservation]
    payment: FactOut[Payment]
    transport: FactOut[Transport]
    recommendedDurationMinutes: FactOut[int]
    bestTime: FactOut[str]
    photoSpots: list[FactOut[PhotoSpot]]
    food: list[FactOut[FoodItem]]
    reviews: list[Review]
    photos: list[PhotoOut]


class PoiListOut(BaseModel):
    # 状态是按哪一天算的
    asOf: date
    pois: list[PoiSummaryOut]


class PoiDetailResponse(BaseModel):
    asOf: date
    poi: PoiDetailOut
