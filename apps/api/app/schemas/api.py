"""对话、规划、分享接口的请求和返回。前端类型在 packages/shared/src/planning.ts，两边要一致。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.llm import LLMErrorOut
from app.schemas.planning import TravelerPreferences


class CreateConversationRequest(BaseModel):
    city: str = "武汉"
    locale: str = "zh-CN"


class ConversationResponse(BaseModel):
    conversationId: str
    status: Literal["active"]


class MessageOut(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    createdAt: datetime
    kind: Literal["question", "itinerary", "failed", "error"] | None = None
    provider: str | None = None
    itineraryVersionId: str | None = None
    # 板块 5B：这条回复带出的那一轮方案，用 GET /api/planning-rounds/{id} 取
    planningRoundId: str | None = None


class ConversationOut(BaseModel):
    conversationId: str
    preferences: TravelerPreferences
    itineraryId: str | None
    messages: list[MessageOut]
    # 这段对话还在规划中的任务（刷新页面后接着显示进度）；没有时为 None
    runningJobId: str | None = None


class SendMessageRequest(BaseModel):
    content: str
    # 界面上选中的模型；不填用 .env 的默认模型
    provider: str | None = None


class SendMessageResponse(BaseModel):
    messageId: int
    planningJobId: str
    status: Literal["queued", "running", "completed", "failed"]


class PlanningStageOut(BaseModel):
    id: str
    label: str


class PlanningJobOut(BaseModel):
    jobId: str
    conversationId: str
    # failed 只表示任务本身出错（模型调用失败等）；行程没通过校验时任务是 completed，kind 是 failed
    status: Literal["queued", "running", "completed", "failed"]
    # 正在做的步骤
    stage: str | None
    # 走过的步骤，按顺序
    stages: list[PlanningStageOut]
    kind: Literal["question", "itinerary", "failed"] | None = None
    reply: str | None = None
    provider: str | None = None
    itineraryVersionId: str | None = None
    planningRoundId: str | None = None
    error: LLMErrorOut | None = None
