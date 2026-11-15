"""规划任务：一条消息交给规划链路后，前端每秒问一次进行到哪一步（2026-11-15 Cecilia 选的轮询）。

任务只存在内存里：后端重启后正在跑的任务就没了，但结果（对话消息、行程版本）已经存进 SQLite。
同一段对话同时只能有一个任务在跑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from app.schemas.llm import LLMErrorOut

JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class PlanningJob:
    id: str
    conversation_id: str
    provider: str | None
    status: JobStatus = "queued"
    # 已经走过的步骤，最后一个是正在做的
    stages: list[str] = field(default_factory=list)
    # completed 时：question / itinerary / failed（行程没通过校验也算任务完成）
    kind: str | None = None
    reply: str | None = None
    used_provider: str | None = None
    itinerary_version_id: str | None = None
    error: LLMErrorOut | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobStore:
    # 内存里最多留这么多个任务，多了删最早的
    MAX_JOBS = 200

    def __init__(self) -> None:
        self._jobs: dict[str, PlanningJob] = {}

    def create(self, conversation_id: str, provider: str | None) -> PlanningJob:
        job = PlanningJob(id=f"job_{uuid4().hex}", conversation_id=conversation_id, provider=provider)
        self._jobs[job.id] = job
        while len(self._jobs) > self.MAX_JOBS:
            self._jobs.pop(next(iter(self._jobs)))
        return job

    def get(self, job_id: str) -> PlanningJob | None:
        return self._jobs.get(job_id)

    def running_for(self, conversation_id: str) -> PlanningJob | None:
        return next(
            (j for j in self._jobs.values() if j.conversation_id == conversation_id and j.status in ("queued", "running")),
            None,
        )
