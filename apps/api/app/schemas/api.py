from typing import Literal

from pydantic import BaseModel


class CreateConversationRequest(BaseModel):
    city: str
    locale: str = "zh-CN"


class ConversationResponse(BaseModel):
    conversationId: str
    status: Literal["active"]


class SendMessageRequest(BaseModel):
    content: str


class PlanningJobResponse(BaseModel):
    messageId: str
    planningJobId: str
    itineraryVersionId: str
    status: Literal["queued", "running", "completed", "failed"]


class PlanningJobStatus(BaseModel):
    jobId: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: str
    progress: float


class PublishShareRequest(BaseModel):
    visibility: Literal["public", "private"] = "public"
    expiresAt: str | None = None


class ShareResponse(BaseModel):
    shareId: str
    slug: str
    url: str
