"""景点的 repository 层（ADR 0003）。

业务代码和接口只调用 PoiRepository 的方法，不写 SQL。
以后换 PostgreSQL 时，新写一个实现这几个方法的类就行。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol

from app.db.sqlite import connect, init_schema
from app.schemas.poi import PoiFile


class PoiRepository(Protocol):
    def list_pois(self, *, district: str | None = None, category: str | None = None) -> list[PoiFile]: ...

    def get_poi(self, poi_id: str) -> PoiFile | None: ...


class SqlitePoiRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self.db_path)
        init_schema(conn)
        return conn

    def list_pois(self, *, district: str | None = None, category: str | None = None) -> list[PoiFile]:
        sql = "SELECT data_json FROM pois"
        where, args = [], []
        if district:
            where.append("district = ?")
            args.append(district)
        if category:
            where.append("category = ?")
            args.append(category)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY sort_order"
        conn = self._conn()
        try:
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
        return [PoiFile.model_validate_json(r["data_json"]) for r in rows]

    def get_poi(self, poi_id: str) -> PoiFile | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT data_json FROM pois WHERE id = ?", (poi_id,)).fetchone()
        finally:
            conn.close()
        return PoiFile.model_validate_json(row["data_json"]) if row else None
