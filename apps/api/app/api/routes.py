"""对话、规划和分享接口。

2026-11-15（板块 2）删掉了 mock 行程：这些接口原来不管请求什么都返回同一份编出来的
武汉三日游。真正的规划链路在板块 5 做，分享页在板块 7 做；在那之前如实返回"还没有"。
"""

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.schemas.api import (
    ConversationResponse,
    CreateConversationRequest,
    PlanningJobResponse,
    PlanningJobStatus,
    PublishShareRequest,
    SendMessageRequest,
    ShareResponse,
)
from app.schemas.itinerary import ItineraryVersion

router = APIRouter(prefix="/api")


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: CreateConversationRequest) -> ConversationResponse:
    return ConversationResponse(conversationId=f"conv_{uuid4().hex}", status="active")


@router.post("/conversations/{conversation_id}/messages", response_model=PlanningJobResponse)
async def send_message(conversation_id: str, request: SendMessageRequest) -> PlanningJobResponse:
    raise HTTPException(status_code=501, detail="行程规划还没有实现（板块 5）")


@router.get("/planning-jobs/{job_id}", response_model=PlanningJobStatus)
async def get_planning_job(job_id: str) -> PlanningJobStatus:
    raise HTTPException(status_code=404, detail=f"没有这个规划任务：{job_id}")


@router.get("/itinerary-versions/{version_id}", response_model=ItineraryVersion)
async def get_itinerary_version(version_id: str) -> ItineraryVersion:
    raise HTTPException(status_code=404, detail=f"没有这份行程：{version_id}")


@router.post("/itinerary-versions/{version_id}/share", response_model=ShareResponse)
async def publish_share_page(version_id: str, request: PublishShareRequest) -> ShareResponse:
    raise HTTPException(status_code=404, detail=f"没有这份行程：{version_id}")


@router.get("/share/{slug}", response_model=ItineraryVersion)
async def get_share_page(slug: str) -> ItineraryVersion:
    raise HTTPException(status_code=404, detail=f"没有这个分享页：{slug}")
