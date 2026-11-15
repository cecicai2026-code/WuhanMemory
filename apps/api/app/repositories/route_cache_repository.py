"""路线缓存的 repository 层。SQL 只出现在这里和 app/db/。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections.abc import Callable
from typing import Any, Protocol

from app.db.sqlite import connect, init_schema
from app.schemas.route import RouteMode, RouteOut


@dataclass
class CachedRoute:
    route: RouteOut
    origin: str
    destination: str
    checkedAt: datetime
    expiresAt: datetime


class RouteCacheRepository(Protocol):
    def get(self, from_id: str, to_id: str, mode: RouteMode) -> CachedRoute | None: ...

    def put(self, from_id: str, to_id: str, mode: RouteMode, entry: CachedRoute, provider: str, raw: dict[str, Any]) -> None: ...


class SqliteRouteCacheRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self.db_path)
        init_schema(conn)
        return conn

    def get(self, from_id: str, to_id: str, mode: RouteMode) -> CachedRoute | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT result_json, origin, destination, checked_at, expires_at FROM route_cache"
                " WHERE from_poi_id = ? AND to_poi_id = ? AND mode = ?",
                (from_id, to_id, mode),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return CachedRoute(
            route=RouteOut.model_validate_json(row["result_json"]),
            origin=row["origin"],
            destination=row["destination"],
            checkedAt=datetime.fromisoformat(row["checked_at"]),
            expiresAt=datetime.fromisoformat(row["expires_at"]),
        )

    def put(self, from_id: str, to_id: str, mode: RouteMode, entry: CachedRoute, provider: str, raw: dict[str, Any]) -> None:
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO route_cache (from_poi_id, to_poi_id, mode, origin, destination, provider,"
                    " result_json, raw_json, checked_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        from_id,
                        to_id,
                        mode,
                        entry.origin,
                        entry.destination,
                        provider,
                        entry.route.model_dump_json(),
                        json.dumps(raw, ensure_ascii=False),
                        entry.checkedAt.isoformat(),
                        entry.expiresAt.isoformat(),
                    ),
                )
        finally:
            conn.close()

    def fill_walking_distances(self, from_raw: Callable[[RouteMode, dict[str, Any]], int | None]) -> int:
        """给板块 3、5 存的旧缓存补上"要走的路"（walkingDistanceMeters），从存着的高德原始返回里读，不发请求。
        只改整理后的结果，原始返回和有效期不变。返回补上了几条。"""
        conn = self._conn()
        filled = 0
        try:
            rows = conn.execute("SELECT from_poi_id, to_poi_id, mode, result_json, raw_json FROM route_cache").fetchall()
            with conn:
                for row in rows:
                    route = RouteOut.model_validate_json(row["result_json"])
                    if route.status != "ok" or route.walkingDistanceMeters is not None:
                        continue
                    meters = from_raw(row["mode"], json.loads(row["raw_json"]))
                    if meters is None:
                        continue
                    route.walkingDistanceMeters = meters
                    conn.execute(
                        "UPDATE route_cache SET result_json = ? WHERE from_poi_id = ? AND to_poi_id = ? AND mode = ?",
                        (route.model_dump_json(), row["from_poi_id"], row["to_poi_id"], row["mode"]),
                    )
                    filled += 1
        finally:
            conn.close()
        return filled
