"""测试用的景点资料。全部是虚构的测试数据（景点名"测试景点"，链接是 example.com），不是真实景点信息。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# 测试里统一假设今天是这一天，过期判断才不会随运行日期变化
TODAY = "2026-11-15"


def good_poi(poi_id: str = "good-sample") -> dict[str, Any]:
    """一份能通过全部检查的景点资料。"""
    poi: dict[str, Any] = {
        "schemaVersion": 1,
        "id": poi_id,
        "name": "测试景点",
        "district": "测试区",
        "category": "museum",
        "tags": ["测试"],
        "sources": [
            {"id": "visit", "type": "field-visit", "title": "测试走访", "accessedAt": "2026-10-01"},
            {
                "id": "official",
                "type": "official-site",
                "title": "测试官网",
                "url": "https://example.com/official",
                "accessedAt": "2026-11-10",
            },
        ],
        "location": {
            "value": {"lng": 114.30, "lat": 30.55, "coordSystem": "GCJ-02"},
            "verification": "confirmed",
            "sourceId": "official",
            "lastCheckedAt": "2026-11-10",
        },
        "address": {"value": "测试地址", "verification": "onsite", "sourceId": "visit", "lastCheckedAt": "2026-10-01"},
        "intro": {"value": "测试简介", "verification": "placeholder", "sourceId": "official", "lastCheckedAt": "2026-11-10"},
        "history": {"value": None, "verification": "todo", "todo": "TODO(Cecilia): 测试"},
        "openingHours": {
            "value": {
                "periods": [{"weekdays": [2, 3, 4, 5, 6, 7], "open": "09:00", "close": "17:00", "lastEntry": "16:00"}],
                "closedWeekdays": [1],
            },
            "verification": "placeholder",
            "sourceId": "official",
            "lastCheckedAt": "2026-11-10",
            "expiresAt": "2027-02-08",
        },
        "ticket": {
            "value": {"free": True},
            "verification": "onsite",
            "sourceId": "visit",
            "lastCheckedAt": "2026-10-01",
            "expiresAt": "2027-03-30",
        },
        "reservation": {
            "value": {"required": True, "how": "测试小程序", "advanceDays": 1},
            "verification": "placeholder",
            "sourceId": "official",
            "lastCheckedAt": "2026-11-10",
            "expiresAt": "2027-02-08",
        },
        "payment": {"value": None, "verification": "todo", "todo": "TODO(Cecilia): 测试"},
        "transport": {
            "value": {"metro": [{"station": "测试站", "line": "测试线", "exit": "A", "walkMinutes": 5}]},
            "verification": "onsite",
            "sourceId": "visit",
            "lastCheckedAt": "2026-10-01",
            "expiresAt": "2027-10-01",
        },
        "recommendedDurationMinutes": {"value": 120, "verification": "onsite", "sourceId": "visit", "lastCheckedAt": "2026-10-01"},
        "bestTime": {"value": None, "verification": "todo", "todo": "TODO(Cecilia): 测试"},
        "photoSpots": [
            {
                "value": {"title": "测试机位", "description": "测试说明", "photo": "sample.jpg"},
                "verification": "onsite",
                "sourceId": "visit",
                "lastCheckedAt": "2026-10-01",
            }
        ],
        "food": [],
        "reviews": [{"author": "测试作者", "relation": "self", "visitedAt": "2026-10-01", "text": "测试评价"}],
        "photos": [
            {"file": "sample.jpg", "caption": "测试照片", "license": "own", "author": "测试作者", "takenAt": "2026-10-01"}
        ],
    }
    return copy.deepcopy(poi)


def clean_poi(poi_id: str, **changes: Any) -> dict[str, Any]:
    """一份校验时不会产生任何警告的测试景点：用到的资料都核实过、没过期。
    开放时间：周二到周日 09:00–17:00，最晚 16:00 入场，周一闭馆；建议游玩 120 分钟。"""
    poi = good_poi(poi_id)
    poi["name"] = f"测试景点{poi_id}"
    for field in ("openingHours", "reservation"):
        poi[field]["verification"] = "confirmed"
    poi["payment"] = {
        "value": {"methods": ["wechat"]},
        "verification": "confirmed",
        "sourceId": "official",
        "lastCheckedAt": "2026-11-10",
        "expiresAt": "2027-05-01",
    }
    for key, value in changes.items():
        poi[key] = value
    return poi


def hours(value: dict[str, Any] | None, verification: str = "confirmed", expires: str = "2027-02-08") -> dict[str, Any]:
    if value is None:
        return {"value": None, "verification": "todo", "todo": "TODO(Cecilia): 测试"}
    return {"value": value, "verification": verification, "sourceId": "official", "lastCheckedAt": "2026-11-10", "expiresAt": expires}


def write_data_dir(root: Path, pois: list[dict[str, Any]], photos: dict[str, list[str]] | None = None) -> Path:
    """在 root 下建一个 data 目录：pois/*.json 和 photos/<id>/ 下的照片文件。"""
    (root / "pois").mkdir(parents=True, exist_ok=True)
    for poi in pois:
        (root / "pois" / f"{poi['id']}.json").write_text(json.dumps(poi, ensure_ascii=False, indent=2), encoding="utf-8")
    for poi_id, files in (photos or {}).items():
        d = root / "photos" / poi_id
        d.mkdir(parents=True, exist_ok=True)
        for f in files:
            (d / f).write_bytes(b"test")
    return root
