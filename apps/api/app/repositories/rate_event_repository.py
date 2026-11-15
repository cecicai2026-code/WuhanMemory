"""公开模式次数限制的记录（板块 7）。SQL 只出现在这里和 app/db/。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.db.sqlite import connect, init_schema

# 只留两天，够算"每小时"和"今天"
_KEEP = timedelta(days=2)


class RateEventRepository(Protocol):
    def add(self, client: str, weight: int, at: datetime) -> None: ...

    def used_by(self, client: str, *, since: datetime) -> int: ...

    def used_total(self, *, since: datetime) -> int: ...


class SqliteRateEventRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self.db_path)
        init_schema(conn)
        return conn

    def add(self, client: str, weight: int, at: datetime) -> None:
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO rate_events (client, weight, created_at) VALUES (?, ?, ?)", (client, weight, at.isoformat())
                )
                conn.execute("DELETE FROM rate_events WHERE created_at < ?", ((at - _KEEP).isoformat(),))
        finally:
            conn.close()

    def _sum(self, sql: str, args: tuple[object, ...]) -> int:
        conn = self._conn()
        try:
            row = conn.execute(sql, args).fetchone()
        finally:
            conn.close()
        return int(row[0] or 0)

    def used_by(self, client: str, *, since: datetime) -> int:
        return self._sum("SELECT SUM(weight) FROM rate_events WHERE client = ? AND created_at >= ?", (client, since.isoformat()))

    def used_total(self, *, since: datetime) -> int:
        return self._sum("SELECT SUM(weight) FROM rate_events WHERE created_at >= ?", (since.isoformat(),))
