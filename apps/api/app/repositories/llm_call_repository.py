"""大模型调用记录的 repository 层。SQL 只出现在这里和 app/db/。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol

from app.db.sqlite import connect, init_schema
from app.services.llm.base import LLMCallRecord


class LLMCallRepository(Protocol):
    def add(self, record: LLMCallRecord) -> None: ...

    def recent(self, *, limit: int = 50, provider: str | None = None) -> list[LLMCallRecord]: ...


class SqliteLLMCallRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self.db_path)
        init_schema(conn)
        return conn

    def add(self, record: LLMCallRecord) -> None:
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO llm_calls (trace_id, task, provider, model, started_at, latency_ms, attempts,"
                    " retried, repaired, ok, error_code, input_tokens, output_tokens)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record.trace_id,
                        record.task,
                        record.provider,
                        record.model,
                        record.started_at,
                        record.latency_ms,
                        record.attempts,
                        int(record.retried),
                        int(record.repaired),
                        int(record.ok),
                        record.error_code,
                        record.input_tokens,
                        record.output_tokens,
                    ),
                )
        finally:
            conn.close()

    def recent(self, *, limit: int = 50, provider: str | None = None) -> list[LLMCallRecord]:
        """最近的记录，新的在前。"""
        sql = (
            "SELECT trace_id, task, provider, model, started_at, latency_ms, attempts, retried, repaired, ok,"
            " error_code, input_tokens, output_tokens FROM llm_calls"
        )
        params: list[object] = []
        if provider:
            sql += " WHERE provider = ?"
            params.append(provider)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [
            LLMCallRecord(
                trace_id=row["trace_id"],
                task=row["task"],
                provider=row["provider"],
                model=row["model"],
                started_at=row["started_at"],
                latency_ms=row["latency_ms"],
                attempts=row["attempts"],
                retried=bool(row["retried"]),
                repaired=bool(row["repaired"]),
                ok=bool(row["ok"]),
                error_code=row["error_code"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
            )
            for row in rows
        ]
