"""分享链接的数据结构（板块 7）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.itinerary import ItineraryVersion


class ShareLink(BaseModel):
    slug: str
    versionId: str
    createdAt: datetime
    # 撤回的时间；没撤回为 None
    revokedAt: datetime | None = None


class ShareLinkOut(ShareLink):
    # 网站上的路径，例如 /s/k3f9x2qa。完整网址由前端按当前网站拼，后端不知道网站开在哪个域名
    path: str

    @classmethod
    def of(cls, link: ShareLink) -> ShareLinkOut:
        return cls(**link.model_dump(), path=f"/s/{link.slug}")


class SharePageOut(BaseModel):
    slug: str
    createdAt: datetime
    # 分享时绑定的那个版本（不可变快照）
    version: ItineraryVersion
