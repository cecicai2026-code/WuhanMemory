"""景点资料的英文译文（中英双语，2026-11-15）。

原始资料只有中文，在 data/pois/<id>.json。英文是译文，单独放在 data/pois/en/<id>.json：

    {
      "id": "yellow-crane-tower",
      "translatedBy": "Claude（AI），未经人工核对",
      "translatedAt": "2026-11-15",
      "texts": {
        "name": {"zh": "黄鹤楼", "en": "Yellow Crane Tower"},
        "intro.value": {"zh": "武汉的城市名片……", "en": "Wuhan's calling card…"},
        "photoSpots.0.value.title": {"zh": "……", "en": "……"}
      }
    }

texts 的键是字段在景点文件里的位置（点号连接，列表用序号）。每条同时存着翻译时的中文原文：
中文资料改了、和这里的 zh 对不上时，这一条译文作废，界面上显示中文，数据检查报一条警告，提醒重新翻译。
所以译文永远不会和中文资料说的不一样。

只翻界面上会显示的文字（TRANSLATABLE）。来源标题、核实备注、TODO 不翻：来源标题是被引用网页的原名，
备注是给 Cecilia 自己看的。开放时间、票价这些结构化的数字不用翻，由前端按语言排版。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.poi import PoiFile

# 会显示在界面上、需要翻译的字段
_PATTERNS = [
    r"name",
    r"district",
    r"tags\.\d+",
    r"address\.value",
    r"intro\.value",
    r"history\.value",
    r"openingHours\.value\.note",
    r"ticket\.value\.items\.\d+\.name",
    r"ticket\.value\.note",
    r"reservation\.value\.(how|note)",
    r"payment\.value\.note",
    r"transport\.value\.metro\.\d+\.(station|line|exit)",
    r"transport\.value\.note",
    r"bestTime\.value",
    r"photoSpots\.\d+\.value\.(title|description)",
    r"food\.\d+\.value\.(name|note)",
    r"reviews\.\d+\.text",
    r"photos\.\d+\.(caption|author|licenseNote)",
    r"operatingStatus\.value\.(note|reopenNote)",
]
TRANSLATABLE = re.compile("^(?:" + "|".join(_PATTERNS) + ")$")


def _walk(obj: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{prefix}.{i}")
    else:
        yield prefix, obj


def translatable_texts(raw: dict[str, Any]) -> dict[str, str]:
    """景点文件里要翻译的文字：{位置: 中文}。空字符串和不是文字的值不算。"""
    return {p: v for p, v in _walk(raw) if TRANSLATABLE.match(p) and isinstance(v, str) and v.strip()}


def _set(obj: Any, path: str, value: str) -> None:
    keys = path.split(".")
    for k in keys[:-1]:
        obj = obj[int(k)] if isinstance(obj, list) else obj[k]
    last = keys[-1]
    if isinstance(obj, list):
        obj[int(last)] = value
    else:
        obj[last] = value


@dataclass
class Translation:
    poi_id: str
    translated_by: str
    translated_at: str
    texts: dict[str, dict[str, str]]


@dataclass
class ApplyResult:
    poi: PoiFile
    used: int = 0
    # 中文改过、译文作废的位置
    stale: list[str] = field(default_factory=list)
    # 有中文、还没有译文的位置
    missing: list[str] = field(default_factory=list)


def load_translation(path: Path) -> Translation:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Translation(
        poi_id=raw["id"],
        translated_by=raw.get("translatedBy", ""),
        translated_at=raw.get("translatedAt", ""),
        texts={k: {"zh": v.get("zh", ""), "en": v.get("en", "")} for k, v in raw.get("texts", {}).items()},
    )


def translations_dir(data_dir: Path) -> Path:
    return data_dir / "pois" / "en"


def _load_dir(data_dir: Path) -> dict[str, Translation]:
    d = translations_dir(data_dir)
    out: dict[str, Translation] = {}
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            t = load_translation(p)
            out[t.poi_id] = t
    return out


@lru_cache(maxsize=4)
def _cached(data_dir: str, stamp: tuple[tuple[str, float], ...]) -> dict[str, Translation]:
    return _load_dir(Path(data_dir))


def load_translations(data_dir: Path) -> dict[str, Translation]:
    """读 data/pois/en/ 下的全部译文。文件改了（修改时间变了）会重新读，不用重启后端。"""
    d = translations_dir(data_dir)
    stamp = tuple((p.name, p.stat().st_mtime) for p in sorted(d.glob("*.json"))) if d.is_dir() else ()
    return _cached(str(data_dir), stamp)


def apply_translation(poi: PoiFile, translation: Translation | None) -> ApplyResult:
    """把一个景点换成英文：有译文、而且译文的中文原文和现在的资料一致的字段换成英文，其余保留中文。"""
    raw = poi.model_dump(mode="json")
    texts = translatable_texts(raw)
    result = ApplyResult(poi=poi)
    if translation is None:
        result.missing = list(texts)
        return result
    for path, zh in texts.items():
        entry = translation.texts.get(path)
        if not entry or not entry.get("en", "").strip():
            result.missing.append(path)
        elif entry.get("zh") != zh:
            result.stale.append(path)
        else:
            _set(raw, path, entry["en"])
            result.used += 1
    result.poi = PoiFile.model_validate(raw)
    return result


def localize_poi(poi: PoiFile, lang: str, data_dir: Path) -> PoiFile:
    """接口和规划用：lang 是 en 时换成英文译文，否则原样返回。"""
    if lang != "en":
        return poi
    return apply_translation(poi, load_translations(data_dir).get(poi.id)).poi


def localize_pois(pois: list[PoiFile], lang: str, data_dir: Path) -> list[PoiFile]:
    if lang != "en":
        return pois
    table = load_translations(data_dir)
    return [apply_translation(p, table.get(p.id)).poi for p in pois]
