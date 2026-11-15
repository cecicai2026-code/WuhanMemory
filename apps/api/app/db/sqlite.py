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

-- 大模型调用记录（板块 4）。网关每调用一次写一行，成功失败都写。板块 6 的双模型对比要用。
-- 只记"用了哪个模型、花了多久、发生了什么"，不存提示词和回答的内容，也不存 key。
CREATE TABLE IF NOT EXISTS llm_calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id      TEXT NOT NULL,
    task          TEXT NOT NULL,         -- 这次调用的用途，例如 ping、extract_preferences
    provider      TEXT NOT NULL,         -- qwen / doubao
    model         TEXT,                  -- 对方返回的真实模型名
    started_at    TEXT NOT NULL,         -- 开始时间，UTC
    latency_ms    INTEGER NOT NULL,      -- 从开始到结束的总时间，含重试之间的等待
    attempts      INTEGER NOT NULL,      -- 一共向模型发了几次请求
    retried       INTEGER NOT NULL,      -- 0 / 1：有没有因为超时、限流、对方出错而重试
    repaired      INTEGER NOT NULL,      -- 0 / 1：有没有因为输出不合格让模型重答
    ok            INTEGER NOT NULL,      -- 0 / 1
    error_code    TEXT,                  -- 失败时的错误类型，例如 timeout、rate_limited、bad_output
    input_tokens  INTEGER,
    output_tokens INTEGER
);

CREATE INDEX IF NOT EXISTS llm_calls_started_idx ON llm_calls (started_at);

-- 对话（板块 5）。preferences_json 是到目前为止抽到的偏好，每条新消息在它的基础上补充。
CREATE TABLE IF NOT EXISTS conversations (
    id               TEXT PRIMARY KEY,
    created_at       TEXT NOT NULL,
    preferences_json TEXT NOT NULL,
    itinerary_id     TEXT                -- 这段对话生成的行程；还没生成时为空
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id      TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role                 TEXT NOT NULL,  -- user / assistant
    content              TEXT NOT NULL,
    created_at           TEXT NOT NULL,
    kind                 TEXT,           -- 回复的种类：question / itinerary / failed / error（用户消息为空）
    asked                TEXT,           -- 反问时问了什么：days、date，逗号分隔
    provider             TEXT,           -- 这条回复用的模型（用户消息为空）
    itinerary_version_id TEXT            -- 这条回复带出的行程版本
);

CREATE INDEX IF NOT EXISTS conversation_messages_conv_idx ON conversation_messages (conversation_id, id);

-- 行程和行程版本（板块 5）。版本存下后不再修改；分享页（板块 7）绑定版本，
-- 双模型对比（板块 6）按版本取结果。没通过校验的版本也存，标 failed。
CREATE TABLE IF NOT EXISTS itineraries (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS itinerary_versions (
    id                TEXT PRIMARY KEY,
    itinerary_id      TEXT NOT NULL REFERENCES itineraries(id) ON DELETE CASCADE,
    version_number    INTEGER NOT NULL,  -- 同一份行程从 1 开始
    created_at        TEXT NOT NULL,
    provider          TEXT NOT NULL,     -- qwen / doubao
    model             TEXT,              -- 对方返回的真实模型名
    validation_status TEXT NOT NULL,     -- passed / warning / failed
    error_count       INTEGER NOT NULL,
    warning_count     INTEGER NOT NULL,
    rounds            INTEGER NOT NULL,  -- 1 或 2（修正过一次）
    data_json         TEXT NOT NULL,     -- 整个版本（ItineraryVersionData）
    UNIQUE (itinerary_id, version_number)
);

-- 规划的"轮"（板块 5B）：一次规划按三种侧重排几份方案，每份存成一个行程版本，这里记下是哪几份、哪些没展示、为什么。
CREATE TABLE IF NOT EXISTS planning_rounds (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    round_number    INTEGER NOT NULL,  -- 同一段对话从 1 开始
    created_at      TEXT NOT NULL,
    data_json       TEXT NOT NULL,     -- 整轮（PlanningRoundData）
    UNIQUE (conversation_id, round_number)
);

-- 双模型对比（板块 6）：同一个请求、同一份偏好和侧重，两个模型各排一份。两份行程各是一个行程版本，这里存数字、差异和对比表。
CREATE TABLE IF NOT EXISTS model_comparisons (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    eval_request_id TEXT,              -- 批量评测时是请求的 id（例如 r01），页面上发起的为空
    data_json       TEXT NOT NULL      -- 整次对比（ModelComparisonData）
);

-- 分享链接（板块 7）：指向一个行程版本（版本不可变）。一个版本同时最多一个没撤回的链接；撤回后再分享换新链接。
CREATE TABLE IF NOT EXISTS share_links (
    slug        TEXT PRIMARY KEY,      -- 8 位随机小写字母和数字
    version_id  TEXT NOT NULL REFERENCES itinerary_versions(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    revoked_at  TEXT                   -- 撤回的时间；没撤回为空
);

-- 同一个版本只能有一个没撤回的链接（两个请求同时分享同一版本时也成立）
CREATE UNIQUE INDEX IF NOT EXISTS share_links_active_idx ON share_links (version_id) WHERE revoked_at IS NULL;
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# 表建好以后又加的列。CREATE TABLE IF NOT EXISTS 不会给已有的表加列，所以在这里补。
_ADDED_COLUMNS = (
    ("conversation_messages", "kind", "TEXT"),
    ("conversation_messages", "asked", "TEXT"),
    # 板块 5B：这条回复带出的那一轮方案
    ("conversation_messages", "planning_round_id", "TEXT"),
)


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for table, column, decl in _ADDED_COLUMNS:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
