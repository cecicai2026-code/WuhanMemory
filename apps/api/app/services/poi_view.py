"""把景点资料变成接口返回的样子：算每条信息的状态、展开来源、给照片加网址。

状态和日期有关（今天过没过 expiresAt），所以每次请求时现算，不存进数据库。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from app.data_quality.rules import REQUIRED_FACTS
from app.schemas.poi import Fact, Photo, PoiFile
from app.schemas.poi_api import (
    FactCounts,
    FactOut,
    FactStatus,
    PhotoOut,
    PoiDetailOut,
    PoiStatus,
    PoiSummaryOut,
    SourceOut,
)

PHOTOS_URL = "/media/photos"
PLACEHOLDER_PHOTOS_URL = "/media/photos-placeholder"


def fact_status(fact: Fact[Any], today: date) -> FactStatus:
    if fact.verification == "todo":
        return "missing"
    if fact.expiresAt is not None and fact.expiresAt < today:
        return "expired"
    if fact.verification == "placeholder":
        return "pending"
    return "verified"


def _all_facts(poi: PoiFile) -> list[Fact[Any]]:
    facts = [getattr(poi, n) for n in REQUIRED_FACTS]
    return [f for f in facts if f is not None] + list(poi.photoSpots) + list(poi.food)


def _counts(poi: PoiFile, today: date) -> FactCounts:
    counts = FactCounts()
    for fact in _all_facts(poi):
        s = fact_status(fact, today)
        setattr(counts, s, getattr(counts, s) + 1)
    return counts


def poi_status(counts: FactCounts) -> PoiStatus:
    if counts.expired:
        return "expired"
    if counts.pending or counts.missing:
        return "pending"
    return "verified"


class PoiPresenter:
    def __init__(self, data_dir: Path, today: date):
        self.data_dir = data_dir
        self.today = today

    def photo(self, poi_id: str, p: Photo) -> PhotoOut:
        placeholder = p.license == "official-placeholder"
        if placeholder:
            exists = (self.data_dir / "photos-placeholder" / poi_id / p.file).is_file()
            url = f"{PLACEHOLDER_PHOTOS_URL}/{poi_id}/{p.file}" if exists else None
        else:
            url = f"{PHOTOS_URL}/{poi_id}/{p.file}"
        return PhotoOut(**p.model_dump(), placeholder=placeholder, url=url)

    def _cover(self, poi: PoiFile) -> PhotoOut | None:
        photos = [self.photo(poi.id, p) for p in poi.photos]
        own = [p for p in photos if not p.placeholder]
        shown = [p for p in photos if p.placeholder and p.url]
        return (own or shown or [None])[0]

    def summary(self, poi: PoiFile) -> PoiSummaryOut:
        assert poi.location is not None and poi.location.value is not None
        counts = _counts(poi, self.today)
        return PoiSummaryOut(
            id=poi.id,
            name=poi.name,
            district=poi.district,
            category=poi.category,
            tags=poi.tags,
            location=poi.location.value,
            status=poi_status(counts),
            counts=counts,
            coverPhoto=self._cover(poi),
        )

    def detail(self, poi: PoiFile) -> PoiDetailOut:
        sources = {s.id: SourceOut(**s.model_dump()) for s in poi.sources}

        def fact(f: Fact[Any] | None) -> dict[str, Any]:
            # 导入前已检查过，这里的字段都存在
            assert f is not None
            return {
                "value": f.value,
                "verification": f.verification,
                "status": fact_status(f, self.today),
                "source": sources.get(f.sourceId) if f.sourceId else None,
                "lastCheckedAt": f.lastCheckedAt,
                "expiresAt": f.expiresAt,
                "todo": f.todo,
                "note": f.note,
            }

        base = self.summary(poi).model_dump()
        return PoiDetailOut.model_validate(
            {
                **base,
                "sources": list(sources.values()),
                **{name: fact(getattr(poi, name)) for name in REQUIRED_FACTS if name != "location"},
                "photoSpots": [fact(f) for f in poi.photoSpots],
                "food": [fact(f) for f in poi.food],
                "reviews": poi.reviews,
                "photos": [self.photo(poi.id, p) for p in poi.photos],
            }
        )


__all__ = ["FactOut", "PoiPresenter", "fact_status", "poi_status"]
