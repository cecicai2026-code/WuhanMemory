from uuid import uuid4

from fastapi import APIRouter

from app.core.config import settings
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
from app.services.llm.gateway import llm_gateway
from app.services.planning.mock_planner import load_mock_itinerary

router = APIRouter(prefix="/api")


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: CreateConversationRequest) -> ConversationResponse:
    return ConversationResponse(conversationId=f"conv_{uuid4().hex}", status="active")


@router.post("/conversations/{conversation_id}/messages", response_model=PlanningJobResponse)
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
) -> PlanningJobResponse:
    await llm_gateway.complete_json(
        system_prompt="Extract travel planning preferences as JSON.",
        user_prompt=request.content,
        schema={"type": "object", "required": ["city", "intent"]},
    )
    return PlanningJobResponse(
        messageId=f"msg_{uuid4().hex}",
        planningJobId=f"job_{uuid4().hex}",
        itineraryVersionId="mock-wuhan-3-days",
        status="completed",
    )


@router.get("/planning-jobs/{job_id}", response_model=PlanningJobStatus)
async def get_planning_job(job_id: str) -> PlanningJobStatus:
    return PlanningJobStatus(
        jobId=job_id,
        status="completed",
        stage="mock_itinerary_ready",
        progress=1.0,
    )


@router.get("/itinerary-versions/{version_id}", response_model=ItineraryVersion)
async def get_itinerary_version(version_id: str) -> ItineraryVersion:
    return load_mock_itinerary()


@router.post("/itinerary-versions/{version_id}/share", response_model=ShareResponse)
async def publish_share_page(
    version_id: str,
    request: PublishShareRequest,
) -> ShareResponse:
    slug = "wuhan-3-days-mock"
    return ShareResponse(
        shareId=f"share_{uuid4().hex}",
        slug=slug,
        url=f"{settings.public_app_url}/s/{slug}",
    )


@router.get("/share/{slug}", response_model=ItineraryVersion)
async def get_share_page(slug: str) -> ItineraryVersion:
    return load_mock_itinerary()
