"""我的行程（板块 7）的数据结构。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.share import ShareLinkOut


class TripVersionSummary(BaseModel):
    id: str
    versionNumber: int
    createdAt: datetime
    title: str
    providerLabel: str
    model: str | None
    validationStatus: Literal["passed", "warning", "failed"]
    errorCount: int
    warningCount: int
    days: int
    startDate: date | None
    poiNames: list[str]
    # 没撤回的分享链接；没有为 None
    share: ShareLinkOut | None = None


class TripItinerary(BaseModel):
    itineraryId: str
    # 侧重（板块 5B）；之前存的版本没有，为 None
    emphasis: str | None
    emphasisLabel: str | None
    # 新版本在前
    versions: list[TripVersionSummary]


class TripConversation(BaseModel):
    conversationId: str
    # 这段对话最近一个版本的时间
    updatedAt: datetime
    # 这段对话里用户的第一句话
    request: str | None
    # 按 经典必去 → 轻松少走路 → 深度文化 排
    itineraries: list[TripItinerary]
