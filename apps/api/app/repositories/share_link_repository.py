"""分享链接的 repository 层（板块 7）。SQL 只出现在这里和 app/db/。

- 链接指向一个行程版本；版本本身不可变，所以分享页不用另外复制数据。
- 一个版本同时最多一个有效链接。撤回后链接永远是撤回状态；再分享就换一个新的。
- 链接是 8 位随机小写字母和数字（去掉容易看错的 0 o 1 l i），不带名字和日期，也猜不出别的链接。
"""

from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.db.sqlite import connect, init_schema
from app.schemas.share import ShareLink

SLUG_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
SLUG_LENGTH = 8
_MAX_TRIES = 10


def random_slug() -> str:
    return "".join(secrets.choice(SLUG_ALPHABET) for _ in range(SLUG_LENGTH))


class ShareLinkRepository(Protocol):
    def create(self, version_id: str) -> ShareLink: ...

    def get(self, slug: str) -> ShareLink | None: ...

    def active_for_version(self, version_id: str) -> ShareLink | None: ...

    def active_by_version(self, version_ids: list[str]) -> dict[str, ShareLink]: ...

    def revoke(self, slug: str) -> ShareLink | None: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row(row: sqlite3.Row) -> ShareLink:
    return ShareLink(
        slug=row["slug"],
        versionId=row["version_id"],
        createdAt=datetime.fromisoformat(row["created_at"]),
        revokedAt=datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None,
    )


class SqliteShareLinkRepository:
    def __init__(self, db_path: Path, make_slug: Callable[[], str] = random_slug):
        self.db_path = db_path
        self.make_slug = make_slug

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self.db_path)
        init_schema(conn)
        return conn

    def create(self, version_id: str) -> ShareLink:
        """给版本建一个链接。已经有没撤回的链接时返回那一个（同时来的两个请求也只会建一个）。"""
        created = _now()
        conn = self._conn()
        try:
            for _ in range(_MAX_TRIES):
                slug = self.make_slug()
                try:
                    with conn:
                        conn.execute(
                            "INSERT INTO share_links (slug, version_id, created_at, revoked_at) VALUES (?, ?, ?, NULL)",
                            (slug, version_id, created.isoformat()),
                        )
                except sqlite3.IntegrityError:
                    active = conn.execute(
                        "SELECT * FROM share_links WHERE version_id = ? AND revoked_at IS NULL", (version_id,)
                    ).fetchone()
                    if active:
                        return _row(active)
                    continue  # 撞上已有的链接，换一个
                return ShareLink(slug=slug, versionId=version_id, createdAt=created)
        finally:
            conn.close()
        raise RuntimeError("连续生成的分享链接都和已有的重复")

    def get(self, slug: str) -> ShareLink | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM share_links WHERE slug = ?", (slug,)).fetchone()
        finally:
            conn.close()
        return _row(row) if row else None

    def active_for_version(self, version_id: str) -> ShareLink | None:
        return self.active_by_version([version_id]).get(version_id)

    def active_by_version(self, version_ids: list[str]) -> dict[str, ShareLink]:
        if not version_ids:
            return {}
        marks = ", ".join("?" for _ in version_ids)
        conn = self._conn()
        try:
            rows = conn.execute(
                f"SELECT * FROM share_links WHERE revoked_at IS NULL AND version_id IN ({marks})"
                " ORDER BY created_at",
                version_ids,
            ).fetchall()
        finally:
            conn.close()
        return {row["version_id"]: _row(row) for row in rows}

    def revoke(self, slug: str) -> ShareLink | None:
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    "UPDATE share_links SET revoked_at = ? WHERE slug = ? AND revoked_at IS NULL",
                    (_now().isoformat(), slug),
                )
            row = conn.execute("SELECT * FROM share_links WHERE slug = ?", (slug,)).fetchone()
        finally:
            conn.close()
        return _row(row) if row else None
