"""把 data/pois/*.json 导入 SQLite。

先跑数据检查，只导入没有 error 的景点；有 warning（例如已过期）的照样导入，界面上显示标记。
每次导入都先清空景点表再重建，JSON 文件才是原始资料。

命令行（在 apps/api 目录下）：
    python -m app.db.import_pois
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

from app.core.config import settings
from app.data_quality.checker import CheckReport, check_data_dir
from app.data_quality.rules import CITY_TZ, REQUIRED_FACTS, today_in_city
from app.db.sqlite import connect, init_schema
from app.schemas.poi import Fact, PoiFile


def _iter_facts(poi: PoiFile):
    for name in REQUIRED_FACTS:
        fact = getattr(poi, name)
        if fact is not None:
            yield name, fact
    if poi.operatingStatus is not None:
        yield "operatingStatus", poi.operatingStatus
    for i, fact in enumerate(poi.photoSpots):
        yield f"photoSpots[{i}]", fact
    for i, fact in enumerate(poi.food):
        yield f"food[{i}]", fact


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def import_pois(conn: sqlite3.Connection, data_dir: Path, today: date) -> tuple[CheckReport, list[str]]:
    """返回检查报告和导入的景点 id。"""
    report = check_data_dir(data_dir, today)
    bad_ids = {i.poi_id for i in report.errors}
    good = [p for p in report.pois if p.id not in bad_ids]
    now = datetime.now(CITY_TZ).isoformat(timespec="seconds")

    init_schema(conn)
    with conn:
        conn.execute("DELETE FROM poi_facts")
        conn.execute("DELETE FROM pois")
        for order, poi in enumerate(good):
            loc = poi.location.value  # 通过检查的景点一定有坐标
            assert loc is not None
            conn.execute(
                "INSERT INTO pois (id, name, district, category, lng, lat, sort_order, tags_json, data_json,"
                " source_file, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    poi.id,
                    poi.name,
                    poi.district,
                    poi.category,
                    loc.lng,
                    loc.lat,
                    order,
                    json.dumps(poi.tags, ensure_ascii=False),
                    poi.model_dump_json(),
                    f"data/pois/{poi.id}.json",
                    now,
                ),
            )
            fact: Fact
            for field, fact in _iter_facts(poi):
                conn.execute(
                    "INSERT INTO poi_facts (poi_id, field, verification, source_id, last_checked_at, expires_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (poi.id, field, fact.verification, fact.sourceId, _iso(fact.lastCheckedAt), _iso(fact.expiresAt)),
                )
    return report, [p.id for p in good]


def main() -> int:
    from app.data_quality.__main__ import format_report

    today = today_in_city()
    conn = connect(settings.database_path)
    try:
        report, imported = import_pois(conn, settings.data_dir, today)
    finally:
        conn.close()
    print(format_report(report, settings.data_dir, today))
    print(f"\n导入 {len(imported)} 个景点到 {settings.database_path}")
    skipped = sorted({i.poi_id for i in report.errors})
    if skipped:
        print("没有导入（有错误）：" + "、".join(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
