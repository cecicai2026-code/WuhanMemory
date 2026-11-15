"""分享接口（板块 7 做）。在那之前如实返回"还没有"。

对话、规划和行程版本的接口在 app/api/planning.py（板块 5）。
"""

from fastapi import APIRouter, HTTPException

from app.schemas.api import PublishShareRequest, ShareResponse

router = APIRouter(prefix="/api")


@router.post("/itinerary-versions/{version_id}/share", response_model=ShareResponse)
async def publish_share_page(version_id: str, request: PublishShareRequest) -> ShareResponse:
    raise HTTPException(status_code=501, detail="分享页还没有实现（板块 7）")


@router.get("/share/{slug}")
async def get_share_page(slug: str) -> None:
    raise HTTPException(status_code=404, detail=f"没有这个分享页：{slug}")
