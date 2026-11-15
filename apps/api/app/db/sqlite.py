"""SQLite 连接和表结构（ADR 0003）。

景点表可以随时删掉重建，原始资料是 data/pois/*.json。
SQL 只出现在 app/db/ 和 app/repositories/ 的 SQLite 实现里。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pois (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    district    TEXT NOT NULL,
    category    TEXT NOT NULL,
    lng         REAL NOT NULL,           -- GCJ-02
    lat         REAL NOT NULL,           -- GCJ-02
    sort_order  INTEGER NOT NULL,        -- 按文件名排序的顺序，列表页按这个排
    tags_json   TEXT NOT NULL,
    data_json   TEXT NOT NULL,           -- 整个景点文件，按 PoiFile 校验过
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS pois_district_category_idx ON pois (district, category);

-- 每条信息的核实方式和日期，单独一张表，方便查"哪些已过期""还剩多少占位"
CREATE TABLE IF NOT EXISTS poi_facts (
    poi_id          TEXT NOT NULL REFERENCES pois(id) ON DELETE CASCADE,
    field           TEXT NOT NULL,       -- 例如 ticket、food[0]
    verification    TEXT NOT NULL,       -- onsite / confirmed / placeholder / todo
    source_id       TEXT,
    last_checked_at TEXT,
    expires_at      TEXT,
    PRIMARY KEY (poi_id, field)
);

CREATE INDEX IF NOT EXISTS poi_facts_expires_idx ON poi_facts (expires_at);

-- 高德路线缓存（板块 3）。一对景点、一种交通方式一行；过期后重新向高德查。
-- 文书里"交通时间要记录核实时间和过期时间"就落在 checked_at 和 expires_at 上。
-- 景点表重建时这张表不动；景点坐标改了，origin / destination 对不上，缓存自然作废。
CREATE TABLE IF NOT EXISTS route_cache (
    from_poi_id TEXT NOT NULL,
    to_poi_id   TEXT NOT NULL,
    mode        TEXT NOT NULL,           -- walk / transit / drive
    origin      TEXT NOT NULL,           -- 发给高德的起点 "lng,lat"（GCJ-02）
    destination TEXT NOT NULL,           -- 发给高德的终点
    provider    TEXT NOT NULL,           -- amap
    result_json TEXT NOT NULL,           -- 整理后的结果（RouteOut）
    raw_json    TEXT NOT NULL,           -- 高德的原始返回，留着核对
    checked_at  TEXT NOT NULL,           -- 向高德查的时间，带时区
    expires_at  TEXT NOT NULL,
    PRIMARY KEY (from_poi_id, to_poi_id, mode)
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
