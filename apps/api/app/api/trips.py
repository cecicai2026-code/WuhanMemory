"""我的行程接口（板块 7）。

- GET /api/trips：/map 上生成过的行程，按对话分组，新的在前；每个版本带没撤回的分享链接。

没有登录：列的是这个数据库里的全部行程。公开模式下要网站主人的口令（app/core/site_policy.py）。
字段说明见 docs/architecture/api-contracts.md 的"我的行程"一节。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.planning import Conversations, Itineraries
from app.api.shares import ShareLinks
from app.core.site_policy import require_owner
from app.schemas.trips import TripConversation
from app.services.trips import TripLister

router = APIRouter(prefix="/api", tags=["trips"])


def get_trip_lister(itineraries: Itineraries, conversations: Conversations, links: ShareLinks) -> TripLister:
    return TripLister(itineraries, conversations, links)


@router.get("/trips", response_model=list[TripConversation], dependencies=[Depends(require_owner)])
async def list_trips(lister: Annotated[TripLister, Depends(get_trip_lister)]) -> list[TripConversation]:
    return lister.list()
