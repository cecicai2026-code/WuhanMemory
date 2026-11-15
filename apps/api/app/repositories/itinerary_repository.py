"""行程和行程版本的 repository 层。SQL 只出现在这里和 app/db/。

版本只能新增，不能修改：没有 update 方法。同一份行程的版本号从 1 开始递增。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel

from app.db.sqlite import connect, init_schema
from app.schemas.itinerary import ItineraryVersion, ItineraryVersionData


class ItineraryRepository(Protocol):
    def create_itinerary(self, conversation_id: str | None) -> str: ...

    def add_version(self, itinerary_id: str, data: ItineraryVersionData) -> ItineraryVersion: ...

    def get_version(self, version_id: str) -> ItineraryVersion | None: ...

    def list_versions(self, itinerary_id: str) -> list[ItineraryVersion]: ...

    def list_conversation_itineraries(self, *, limit: int = 200) -> list[ItineraryRef]: ...


class ItineraryRef(BaseModel):
    """一份行程本身（不含版本）。"""

    id: str
    conversationId: str | None
    createdAt: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SqliteItineraryRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self.db_path)
        init_schema(conn)
        return conn

    def create_itinerary(self, conversation_id: str | None) -> str:
        itinerary_id = f"itin_{uuid4().hex}"
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO itineraries (id, conversation_id, created_at) VALUES (?, ?, ?)",
                    (itinerary_id, conversation_id, _now().isoformat()),
                )
        finally:
            conn.close()
        return itinerary_id

    def add_version(self, itinerary_id: str, data: ItineraryVersionData) -> ItineraryVersion:
        version_id = f"ver_{uuid4().hex}"
        created = _now()
        report = data.validation
        conn = self._conn()
        try:
            with conn:
                row = conn.execute(
                    "SELECT COALESCE(MAX(version_number), 0) + 1 FROM itinerary_versions WHERE itinerary_id = ?",
                    (itinerary_id,),
                ).fetchone()
                number = int(row[0])
                conn.execute(
                    "INSERT INTO itinerary_versions (id, itinerary_id, version_number, created_at, provider, model,"
                    " validation_status, error_count, warning_count, rounds, data_json)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        version_id,
                        itinerary_id,
                        number,
                        created.isoformat(),
                        data.planner.provider,
                        data.planner.model,
                        report.status,
                        len(report.errors),
                        len(report.warnings),
                        data.planner.rounds,
                        data.model_dump_json(),
                    ),
                )
        finally:
            conn.close()
        return ItineraryVersion(
            **data.model_dump(), id=version_id, itineraryId=itinerary_id, versionNumber=number, createdAt=created
        )

    def _row_to_version(self, row: sqlite3.Row) -> ItineraryVersion:
        data = ItineraryVersionData.model_validate_json(row["data_json"])
        return ItineraryVersion(
            **data.model_dump(),
            id=row["id"],
            itineraryId=row["itinerary_id"],
            versionNumber=row["version_number"],
            createdAt=datetime.fromisoformat(row["created_at"]),
        )

    def get_version(self, version_id: str) -> ItineraryVersion | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM itinerary_versions WHERE id = ?", (version_id,)).fetchone()
        finally:
            conn.close()
        return self._row_to_version(row) if row else None

    def list_versions(self, itinerary_id: str) -> list[ItineraryVersion]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM itinerary_versions WHERE itinerary_id = ? ORDER BY version_number",
                (itinerary_id,),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_version(r) for r in rows]

    def list_conversation_itineraries(self, *, limit: int = 200) -> list[ItineraryRef]:
        """属于某段对话（/map 上生成）的行程，新的在前。/compare 产生的行程不属于对话，不在里面。"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM itineraries WHERE conversation_id IS NOT NULL ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            conn.close()
        return [
            ItineraryRef(id=r["id"], conversationId=r["conversation_id"], createdAt=datetime.fromisoformat(r["created_at"]))
            for r in rows
        ]
