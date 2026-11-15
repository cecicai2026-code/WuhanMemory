"""双模型对比的 repository 层（板块 6）。一次对比存下后不再修改。"""

from __future__ import annotations

import sqlite3
from app.services.planning.emphasis import EMPHASES
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.db.sqlite import connect, init_schema
from app.schemas.comparison import ModelComparison, ModelComparisonData, ModelComparisonSummary, SideBrief


class ModelComparisonRepository(Protocol):
    def add(self, data: ModelComparisonData) -> ModelComparison: ...

    def get(self, comparison_id: str) -> ModelComparison | None: ...

    def list(self, *, limit: int = 50) -> list[ModelComparisonSummary]: ...


def summary_of(c: ModelComparison) -> ModelComparisonSummary:
    return ModelComparisonSummary(
        id=c.id,
        createdAt=c.createdAt,
        request=c.request,
        # 侧重名按当前请求的语言（中英双语）；认不出的侧重用存下来的名字
        emphasisLabel=EMPHASES[c.emphasis].label if c.emphasis in EMPHASES else c.emphasisLabel,
        evalRequestId=c.evalRequestId,
        sides=[
            SideBrief(
                providerLabel=s.providerLabel,
                model=s.model,
                error=s.quality is None,
                firstPassed=s.quality.firstPassed if s.quality else None,
                finalPassed=s.quality.finalPassed if s.quality else None,
            )
            for s in c.sides
        ],
    )


def _without_unanswered_model(data: ModelComparisonData) -> ModelComparisonData:
    """模型没排出来的一边，对方没回答过，不知道真实模型名。2026-11-15 的一次评测里这一格存成了豆包的推理接入点 ID
    （那时取的是失败调用里记的模型设置，已改），读出来时一律清空，接入点 ID 不给前端。"""
    sides = [s.model_copy(update={"model": None}) if s.quality is None else s for s in data.sides]
    return data.model_copy(update={"sides": sides})


class SqliteModelComparisonRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self.db_path)
        init_schema(conn)
        return conn

    def add(self, data: ModelComparisonData) -> ModelComparison:
        comparison_id = f"cmp_{uuid4().hex}"
        created = datetime.now(timezone.utc)
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO model_comparisons (id, created_at, eval_request_id, data_json) VALUES (?, ?, ?, ?)",
                    (comparison_id, created.isoformat(), data.evalRequestId, data.model_dump_json()),
                )
        finally:
            conn.close()
        return ModelComparison(**data.model_dump(), id=comparison_id, createdAt=created)

    @staticmethod
    def _row(row: sqlite3.Row) -> ModelComparison:
        data = _without_unanswered_model(ModelComparisonData.model_validate_json(row["data_json"]))
        return ModelComparison(**data.model_dump(), id=row["id"], createdAt=datetime.fromisoformat(row["created_at"]))

    def get(self, comparison_id: str) -> ModelComparison | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM model_comparisons WHERE id = ?", (comparison_id,)).fetchone()
        finally:
            conn.close()
        return self._row(row) if row else None

    def list(self, *, limit: int = 50) -> list[ModelComparisonSummary]:
        """新的在前。"""
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM model_comparisons ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        finally:
            conn.close()
        return [summary_of(self._row(r)) for r in rows]
