"""规划"轮"的 repository 层（板块 5B）。一轮存下后不再修改。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.db.sqlite import connect, init_schema
from app.schemas.itinerary import PlanningRound, PlanningRoundData


class PlanningRoundRepository(Protocol):
    def add_round(self, data: PlanningRoundData) -> PlanningRound: ...

    def get_round(self, round_id: str) -> PlanningRound | None: ...

    def list_rounds(self, conversation_id: str) -> list[PlanningRound]: ...


class SqlitePlanningRoundRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self.db_path)
        init_schema(conn)
        return conn

    def add_round(self, data: PlanningRoundData) -> PlanningRound:
        round_id = f"round_{uuid4().hex}"
        created = datetime.now(timezone.utc)
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO planning_rounds (id, conversation_id, round_number, created_at, data_json)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (round_id, data.conversationId, data.roundNumber, created.isoformat(), data.model_dump_json()),
                )
        finally:
            conn.close()
        return PlanningRound(**data.model_dump(), id=round_id, createdAt=created)

    @staticmethod
    def _row(row: sqlite3.Row) -> PlanningRound:
        data = PlanningRoundData.model_validate_json(row["data_json"])
        return PlanningRound(**data.model_dump(), id=row["id"], createdAt=datetime.fromisoformat(row["created_at"]))

    def get_round(self, round_id: str) -> PlanningRound | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM planning_rounds WHERE id = ?", (round_id,)).fetchone()
        finally:
            conn.close()
        return self._row(row) if row else None

    def list_rounds(self, conversation_id: str) -> list[PlanningRound]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM planning_rounds WHERE conversation_id = ? ORDER BY round_number", (conversation_id,)
            ).fetchall()
        finally:
            conn.close()
        return [self._row(r) for r in rows]
