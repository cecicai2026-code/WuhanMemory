"""对话和规划接口（板块 5）。

- POST /api/conversations：新建对话。
- GET  /api/conversations/{id}：对话里的消息和抽到的偏好（刷新页面后接着显示）。
- POST /api/conversations/{id}/messages：发一条消息，带上界面上选中的模型；返回规划任务 id。
- GET  /api/planning-jobs/{id}：规划进行到哪一步、结果是什么。前端每秒问一次。
- GET  /api/itinerary-versions/{id}：一个行程版本（不可变）。
- GET  /api/planning-rounds/{id}：一轮方案（板块 5B）：展示的几份的版本、比较表，以及没展示的是哪几份、为什么。

字段说明见 docs/architecture/api-contracts.md 的"对话和规划"一节。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.config import settings
from app.core.site_policy import rate_limited
from app.data_quality.rules import today_in_city
from app.repositories.conversation_repository import ConversationRepository, SqliteConversationRepository
from app.repositories.itinerary_repository import ItineraryRepository, SqliteItineraryRepository
from app.repositories.planning_round_repository import PlanningRoundRepository, SqlitePlanningRoundRepository
from app.repositories.poi_repository import SqlitePoiRepository
from app.repositories.route_cache_repository import SqliteRouteCacheRepository
from app.schemas.api import (
    ConversationOut,
    ConversationResponse,
    CreateConversationRequest,
    MessageOut,
    PlanningJobOut,
    PlanningStageOut,
    SendMessageRequest,
    SendMessageResponse,
)
from app.schemas.itinerary import ItineraryVersion, PlanningRoundOut
from app.schemas.llm import LLMErrorOut
from app.services.llm.errors import LLMError
from app.services.llm.factory import get_llm_gateway
from app.services.planning.jobs import JobStore, PlanningJob
from app.services.planning.metrics import compare_plans
from app.services.planning.pipeline import STAGE_LABELS, PlanningPipeline
from app.services.routing.amap import AmapRouteProvider
from app.services.routing.service import RouteService

logger = logging.getLogger("wuhanmemory.planning")

router = APIRouter(prefix="/api", tags=["planning"])

PipelineFactory = Callable[[], AbstractAsyncContextManager[PlanningPipeline]]


@asynccontextmanager
async def _default_pipeline() -> AsyncIterator[PlanningPipeline]:
    # 任务在回应发出之后才跑，所以自己开一个 httpx 客户端，不用请求范围里的那个
    async with httpx.AsyncClient() as client:
        pois = SqlitePoiRepository(settings.database_path)
        routes = RouteService(
            pois,
            AmapRouteProvider(settings.amap_web_service_key, settings.amap_base_url, client),
            SqliteRouteCacheRepository(settings.database_path),
        )
        yield PlanningPipeline(
            gateway=get_llm_gateway(),
            pois=pois,
            routes=routes,
            itineraries=SqliteItineraryRepository(settings.database_path),
            conversations=SqliteConversationRepository(settings.database_path),
            rounds=SqlitePlanningRoundRepository(settings.database_path),
            today=today_in_city,
        )


def get_pipeline_factory() -> PipelineFactory:
    return _default_pipeline


@lru_cache
def get_job_store() -> JobStore:
    return JobStore()


def get_conversations() -> ConversationRepository:
    return SqliteConversationRepository(settings.database_path)


def get_itineraries() -> ItineraryRepository:
    return SqliteItineraryRepository(settings.database_path)


def get_rounds() -> PlanningRoundRepository:
    return SqlitePlanningRoundRepository(settings.database_path)


Rounds = Annotated[PlanningRoundRepository, Depends(get_rounds)]
Conversations = Annotated[ConversationRepository, Depends(get_conversations)]
Itineraries = Annotated[ItineraryRepository, Depends(get_itineraries)]
Jobs = Annotated[JobStore, Depends(get_job_store)]
Factory = Annotated[PipelineFactory, Depends(get_pipeline_factory)]


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: CreateConversationRequest, conversations: Conversations) -> ConversationResponse:
    conv = conversations.create()
    return ConversationResponse(conversationId=conv.id, status="active")


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: str, conversations: Conversations, jobs: Jobs) -> ConversationOut:
    conv = conversations.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail=f"没有这段对话：{conversation_id}")
    running = jobs.running_for(conv.id)
    return ConversationOut(
        conversationId=conv.id,
        preferences=conv.preferences,
        itineraryId=conv.itineraryId,
        messages=[MessageOut(**m.model_dump()) for m in conversations.messages(conv.id)],
        runningJobId=running.id if running else None,
    )


async def _run(job: PlanningJob, content: str, factory: PipelineFactory, conversations: ConversationRepository) -> None:
    job.status = "running"

    def on_stage(name: str) -> None:
        job.stages.append(name)

    try:
        async with factory() as pipeline:
            outcome = await pipeline.handle(job.conversation_id, content, provider=job.provider, on_stage=on_stage)
    except LLMError as exc:
        job.error = LLMErrorOut(code=exc.code, message=exc.message, retryable=exc.retryable, provider=exc.provider)
        job.status = "failed"
        conversations.add_message(
            job.conversation_id, "assistant", f"模型调用出错：{exc.message}", kind="error", provider=exc.provider
        )
        return
    except Exception as exc:  # 没预料到的错误：只记类型名，不把内容（可能带 key）返回给前端
        logger.exception("规划任务出错")
        job.error = LLMErrorOut(code="internal_error", message=f"程序出错（{type(exc).__name__}），请看后端日志。", retryable=False)
        job.status = "failed"
        conversations.add_message(job.conversation_id, "assistant", job.error.message, kind="error")
        return
    job.kind = outcome.kind
    job.reply = outcome.reply
    job.used_provider = outcome.provider
    job.itinerary_version_id = outcome.version.id if outcome.version else None
    job.planning_round_id = outcome.round.id if outcome.round else None
    job.status = "completed"


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    status_code=202,
    # 公开模式下限次数（app/core/site_policy.py）
    dependencies=[Depends(rate_limited(1))],
)
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    background: BackgroundTasks,
    conversations: Conversations,
    jobs: Jobs,
    factory: Factory,
) -> SendMessageResponse:
    if conversations.get(conversation_id) is None:
        raise HTTPException(status_code=404, detail=f"没有这段对话：{conversation_id}")
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息是空的")
    running = jobs.running_for(conversation_id)
    if running is not None:
        raise HTTPException(status_code=409, detail=f"上一条消息还在规划中（{running.id}），等它完成再发")
    message = conversations.add_message(conversation_id, "user", content)
    job = jobs.create(conversation_id, request.provider)
    background.add_task(_run, job, content, factory, conversations)
    return SendMessageResponse(messageId=message.id, planningJobId=job.id, status=job.status)


@router.get("/planning-jobs/{job_id}", response_model=PlanningJobOut)
async def get_planning_job(job_id: str, jobs: Jobs) -> PlanningJobOut:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"没有这个规划任务：{job_id}（后端重启过的话，任务会丢，结果在对话里）")
    return PlanningJobOut(
        jobId=job.id,
        conversationId=job.conversation_id,
        status=job.status,
        stage=job.stages[-1] if job.stages else None,
        stages=[PlanningStageOut(id=s, label=STAGE_LABELS.get(s, s)) for s in job.stages],
        kind=job.kind,  # type: ignore[arg-type]
        reply=job.reply,
        provider=job.used_provider or job.provider,
        itineraryVersionId=job.itinerary_version_id,
        planningRoundId=job.planning_round_id,
        error=job.error,
    )


@router.get("/itinerary-versions/{version_id}", response_model=ItineraryVersion)
async def get_itinerary_version(version_id: str, itineraries: Itineraries) -> ItineraryVersion:
    version = itineraries.get_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"没有这份行程：{version_id}")
    return version


@router.get("/planning-rounds/{round_id}", response_model=PlanningRoundOut)
async def get_planning_round(round_id: str, rounds: Rounds, itineraries: Itineraries) -> PlanningRoundOut:
    found = rounds.get_round(round_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"没有这一轮方案：{round_id}")
    shown = [p for p in found.plans if p.shown and p.versionId]
    versions = [v for v in (itineraries.get_version(p.versionId) for p in shown if p.versionId) if v is not None]
    comparison = compare_plans([p.label for p in shown], versions) if versions else None
    return PlanningRoundOut(**found.model_dump(), versions=versions, comparison=comparison)
