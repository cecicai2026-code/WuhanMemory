"""对话的 repository 层：对话、到目前为止抽到的偏好、每条消息。SQL 只出现在这里和 app/db/。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel

from app.db.sqlite import connect, init_schema
from app.schemas.planning import TravelerPreferences

Role = Literal["user", "assistant"]
# 回复的种类：question 反问；itinerary 带出行程（通过或有警告）；failed 修正后仍未通过；error 模型或程序出错
ReplyKind = Literal["question", "itinerary", "failed", "error"]


class StoredMessage(BaseModel):
    id: int
    role: Role
    content: str
    createdAt: datetime
    kind: ReplyKind | None = None
    # 反问时问了什么，例如 ["days", "date"]
    asked: list[str] = []
    provider: str | None = None
    itineraryVersionId: str | None = None
    # 板块 5B：这条回复带出的那一轮方案
    planningRoundId: str | None = None


class Conversation(BaseModel):
    id: str
    createdAt: datetime
    preferences: TravelerPreferences
    itineraryId: str | None


class ConversationRepository(Protocol):
    def create(self) -> Conversation: ...

    def get(self, conversation_id: str) -> Conversation | None: ...

    def save_preferences(self, conversation_id: str, preferences: TravelerPreferences) -> None: ...

    def set_itinerary(self, conversation_id: str, itinerary_id: str) -> None: ...

    def add_message(
        self,
        conversation_id: str,
        role: Role,
        content: str,
        *,
        kind: ReplyKind | None = None,
        asked: list[str] | None = None,
        provider: str | None = None,
        itinerary_version_id: str | None = None,
        planning_round_id: str | None = None,
    ) -> StoredMessage: ...

    def messages(self, conversation_id: str) -> list[StoredMessage]: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SqliteConversationRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self.db_path)
        init_schema(conn)
        return conn

    def create(self) -> Conversation:
        conv = Conversation(
            id=f"conv_{uuid4().hex}", createdAt=_now(), preferences=TravelerPreferences(), itineraryId=None
        )
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO conversations (id, created_at, preferences_json, itinerary_id) VALUES (?, ?, ?, NULL)",
                    (conv.id, conv.createdAt.isoformat(), conv.preferences.model_dump_json()),
                )
        finally:
            conn.close()
        return conv

    def get(self, conversation_id: str) -> Conversation | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return Conversation(
            id=row["id"],
            createdAt=datetime.fromisoformat(row["created_at"]),
            preferences=TravelerPreferences.model_validate_json(row["preferences_json"]),
            itineraryId=row["itinerary_id"],
        )

    def _update(self, sql: str, params: tuple[object, ...]) -> None:
        conn = self._conn()
        try:
            with conn:
                conn.execute(sql, params)
        finally:
            conn.close()

    def save_preferences(self, conversation_id: str, preferences: TravelerPreferences) -> None:
        self._update(
            "UPDATE conversations SET preferences_json = ? WHERE id = ?",
            (preferences.model_dump_json(), conversation_id),
        )

    def set_itinerary(self, conversation_id: str, itinerary_id: str) -> None:
        self._update("UPDATE conversations SET itinerary_id = ? WHERE id = ?", (itinerary_id, conversation_id))

    def add_message(
        self,
        conversation_id: str,
        role: Role,
        content: str,
        *,
        kind: ReplyKind | None = None,
        asked: list[str] | None = None,
        provider: str | None = None,
        itinerary_version_id: str | None = None,
        planning_round_id: str | None = None,
    ) -> StoredMessage:
        created = _now()
        asked = asked or []
        conn = self._conn()
        try:
            with conn:
                cur = conn.execute(
                    "INSERT INTO conversation_messages (conversation_id, role, content, created_at, kind, asked, provider,"
                    " itinerary_version_id, planning_round_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        conversation_id,
                        role,
                        content,
                        created.isoformat(),
                        kind,
                        ",".join(asked) or None,
                        provider,
                        itinerary_version_id,
                        planning_round_id,
                    ),
                )
                message_id = int(cur.lastrowid or 0)
        finally:
            conn.close()
        return StoredMessage(
            id=message_id,
            role=role,
            content=content,
            createdAt=created,
            kind=kind,
            asked=asked,
            provider=provider,
            itineraryVersionId=itinerary_version_id,
            planningRoundId=planning_round_id,
        )

    def messages(self, conversation_id: str) -> list[StoredMessage]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM conversation_messages WHERE conversation_id = ? ORDER BY id", (conversation_id,)
            ).fetchall()
        finally:
            conn.close()
        return [
            StoredMessage(
                id=r["id"],
                role=r["role"],
                content=r["content"],
                createdAt=datetime.fromisoformat(r["created_at"]),
                kind=r["kind"],
                asked=r["asked"].split(",") if r["asked"] else [],
                provider=r["provider"],
                itineraryVersionId=r["itinerary_version_id"],
                planningRoundId=r["planning_round_id"],
            )
            for r in rows
        ]
