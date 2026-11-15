"""双模型对比接口（板块 6）。

- POST /api/comparisons：发起一次对比（请求 + 侧重），返回任务 id。一次只能跑一个对比，免得不小心重复花 token。
- GET  /api/comparison-jobs/{id}：对比进行到哪一步（共用的步骤，以及每边各自的步骤）、结果是哪次对比。前端每秒问一次。
- GET  /api/comparisons：历史对比，新的在前。
- GET  /api/comparisons/{id}：一次对比：每边的数字、差异、对比表，以及两边的行程版本。

字段说明见 docs/architecture/api-contracts.md 的"双模型对比"一节。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.site_policy import rate_limited
from app.api.planning import Factory, Itineraries, PipelineFactory
from app.core.config import settings
from app.repositories.itinerary_repository import ItineraryRepository
from app.repositories.model_comparison_repository import ModelComparisonRepository, SqliteModelComparisonRepository
from app.schemas.api import PlanningStageOut
from app.schemas.comparison import ModelComparison, ModelComparisonSummary
from app.schemas.itinerary import ItineraryVersion
from app.schemas.llm import LLMErrorOut
from app.services.llm.errors import LLMError
from app.services.llm.factory import get_llm_gateway
from app.services.llm.gateway import LLMGateway
from app.services.planning.compare_runner import DEFAULT_PROVIDERS, ModelComparer, NeedsMoreInfo
from app.services.planning.emphasis import EMPHASES
from app.services.planning.pipeline import STAGE_LABELS

logger = logging.getLogger("wuhanmemory.compare")

router = APIRouter(prefix="/api", tags=["comparisons"])

COMPARE_STAGE_LABELS = {
    **STAGE_LABELS,
    "understanding": "理解需求（抽一次偏好，两边共用）",
    "done": "排完了",
    "saving": "算数字、保存",
}

JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class CompareJob:
    id: str
    request: str
    emphasis: str
    status: JobStatus = "queued"
    # 共用的步骤（抽偏好、保存）
    stages: list[str] = field(default_factory=list)
    # 每边各自的步骤
    side_stages: dict[str, list[str]] = field(default_factory=dict)
    comparison_id: str | None = None
    error: LLMErrorOut | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CompareJobStore:
    MAX_JOBS = 100

    def __init__(self) -> None:
        self._jobs: dict[str, CompareJob] = {}

    def create(self, request: str, emphasis: str) -> CompareJob:
        job = CompareJob(id=f"cjob_{uuid4().hex}", request=request, emphasis=emphasis,
                         side_stages={p: [] for p in DEFAULT_PROVIDERS})
        self._jobs[job.id] = job
        while len(self._jobs) > self.MAX_JOBS:
            self._jobs.pop(next(iter(self._jobs)))
        return job

    def get(self, job_id: str) -> CompareJob | None:
        return self._jobs.get(job_id)

    def running(self) -> CompareJob | None:
        return next((j for j in self._jobs.values() if j.status in ("queued", "running")), None)


@lru_cache
def get_compare_jobs() -> CompareJobStore:
    return CompareJobStore()


def get_comparisons() -> ModelComparisonRepository:
    return SqliteModelComparisonRepository(settings.database_path)


def get_gateway() -> LLMGateway:
    return get_llm_gateway()


CompareJobs = Annotated[CompareJobStore, Depends(get_compare_jobs)]
Gateway = Annotated[LLMGateway, Depends(get_gateway)]
Comparisons = Annotated[ModelComparisonRepository, Depends(get_comparisons)]


# ---------- 请求和返回 ----------


class CompareRequest(BaseModel):
    request: str = Field(min_length=1, max_length=500)
    emphasis: str = "classic"


class CompareStartOut(BaseModel):
    jobId: str
    status: JobStatus


class SideProgressOut(BaseModel):
    provider: str
    label: str
    stages: list[PlanningStageOut]


class CompareJobOut(BaseModel):
    jobId: str
    status: JobStatus
    request: str
    emphasis: str
    stages: list[PlanningStageOut]
    sides: list[SideProgressOut]
    comparisonId: str | None
    error: LLMErrorOut | None


class ModelComparisonOut(ModelComparison):
    # 两边的行程版本，顺序和 sides 一样；没排出来的一边为 null
    versions: list[ItineraryVersion | None]


def _stages(names: list[str]) -> list[PlanningStageOut]:
    return [PlanningStageOut(id=s, label=COMPARE_STAGE_LABELS.get(s, s)) for s in names]


# ---------- 任务 ----------


async def _run(job: CompareJob, factory: PipelineFactory, comparisons: ModelComparisonRepository) -> None:
    job.status = "running"

    def on_progress(provider: str | None, stage: str) -> None:
        if provider is None:
            job.stages.append(stage)
        else:
            job.side_stages.setdefault(provider, []).append(stage)

    try:
        async with factory() as pipeline:
            result = await ModelComparer(pipeline, comparisons).compare(
                job.request, emphasis=job.emphasis, on_progress=on_progress
            )
    except NeedsMoreInfo as exc:
        job.error = LLMErrorOut(code="needs_days", message=str(exc), retryable=False)
        job.status = "failed"
        return
    except LLMError as exc:
        job.error = LLMErrorOut(code=exc.code, message=f"抽偏好时模型出错：{exc.message}", retryable=exc.retryable,
                                provider=exc.provider)
        job.status = "failed"
        return
    except Exception as exc:  # 没预料到的错误：只记类型名，不把内容返回给前端
        logger.exception("对比任务出错")
        job.error = LLMErrorOut(code="internal_error", message=f"程序出错（{type(exc).__name__}），请看后端日志。", retryable=False)
        job.status = "failed"
        return
    job.comparison_id = result.id
    job.status = "completed"


@router.post(
    "/comparisons",
    response_model=CompareStartOut,
    status_code=202,
    # 公开模式下限次数，两个模型各排一份，算 2 次（app/core/site_policy.py）
    dependencies=[Depends(rate_limited(2))],
)
async def start_comparison(
    body: CompareRequest,
    background: BackgroundTasks,
    jobs: CompareJobs,
    factory: Factory,
    comparisons: Comparisons,
    gateway: Gateway,
) -> CompareStartOut:
    text = body.request.strip()
    if not text:
        raise HTTPException(status_code=400, detail="请求是空的")
    if body.emphasis not in EMPHASES:
        raise HTTPException(status_code=400, detail=f"没有这种侧重：{body.emphasis}")
    configured = {p.id: p.configured for p in gateway.providers()}
    missing = [p for p in DEFAULT_PROVIDERS if not configured.get(p)]
    if missing:
        raise HTTPException(status_code=400, detail=f"这些模型还没配置，没法对比：{'、'.join(missing)}")
    running = jobs.running()
    if running is not None:
        raise HTTPException(status_code=409, detail=f"上一次对比还在跑（{running.id}），等它完成再发")
    job = jobs.create(text, body.emphasis)
    background.add_task(_run, job, factory, comparisons)
    return CompareStartOut(jobId=job.id, status=job.status)


@router.get("/comparison-jobs/{job_id}", response_model=CompareJobOut)
async def get_comparison_job(job_id: str, jobs: CompareJobs, gateway: Gateway) -> CompareJobOut:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"没有这个对比任务：{job_id}（后端重启过的话，任务会丢，跑完的结果在历史对比里）")
    labels = {p.id: p.label for p in gateway.providers()}
    return CompareJobOut(
        jobId=job.id,
        status=job.status,
        request=job.request,
        emphasis=job.emphasis,
        stages=_stages(job.stages),
        sides=[SideProgressOut(provider=p, label=labels.get(p, p), stages=_stages(s)) for p, s in job.side_stages.items()],
        comparisonId=job.comparison_id,
        error=job.error,
    )


@router.get("/comparisons", response_model=list[ModelComparisonSummary])
async def list_comparisons(comparisons: Comparisons, limit: int = 50) -> list[ModelComparisonSummary]:
    return comparisons.list(limit=max(1, min(limit, 200)))


@router.get("/comparisons/{comparison_id}", response_model=ModelComparisonOut)
async def get_comparison(comparison_id: str, comparisons: Comparisons, itineraries: Itineraries) -> ModelComparisonOut:
    found = comparisons.get(comparison_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"没有这次对比：{comparison_id}")
    repo: ItineraryRepository = itineraries
    versions = [repo.get_version(s.versionId) if s.versionId else None for s in found.sides]
    return ModelComparisonOut(**found.model_dump(), versions=versions)
