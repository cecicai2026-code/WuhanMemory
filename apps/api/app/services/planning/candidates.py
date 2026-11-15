"""从景点库筛候选，整理成给模型看的清单。

模型只能从这份清单里选景点，用 id 引用；不在清单里的 id，校验时算"景点不存在"。

筛选规则：
- 暂停开放的去掉（资料里 operatingStatus 是 closed-temporarily）。用户点名想去的话，告诉他现在不开。
- 用户说不想去的去掉（按名字匹配）。
- 其余全部保留，按兴趣匹配的多少排序。景点库现在只有 10 个，规划策略要求候选至少是要排的景点数的 2 倍，
  所以眼下不按兴趣砍掉景点，只把对得上的排在前面、标出对得上哪些兴趣。景点多了以后再加上限。
- 用户点名想去的，在库里的标"必去"；不在库里的告诉用户没法安排，不让模型去编。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.schemas.planning import TravelerPreferences
from app.schemas.poi import PoiFile
from app.services.planning.interests import matched_interests, poi_interests


@dataclass
class Candidates:
    pois: dict[str, PoiFile]
    must_visit: list[str] = field(default_factory=list)
    # 用户点名、但景点库里没有的
    not_in_library: list[str] = field(default_factory=list)
    avoided: list[str] = field(default_factory=list)
    # 用户点名、但现在暂停开放的（景点名）
    closed_requested: list[str] = field(default_factory=list)


def is_closed(poi: PoiFile) -> bool:
    """资料里写着暂停开放。这条资料过期了也照样算关着，等重新核实后改资料。"""
    fact = poi.operatingStatus
    return fact is not None and fact.value is not None and fact.value.code == "closed-temporarily"


def _matches(name: str, poi: PoiFile) -> bool:
    name = name.strip()
    return bool(name) and (name in poi.name or poi.name in name)


def select_candidates(library: list[PoiFile], prefs: TravelerPreferences) -> Candidates:
    kept: list[PoiFile] = []
    avoided: list[str] = []
    closed_requested: list[str] = []
    for poi in library:
        if is_closed(poi):
            if any(_matches(n, poi) for n in prefs.mustVisit):
                closed_requested.append(poi.name)
        elif any(_matches(n, poi) for n in prefs.avoid):
            avoided.append(poi.id)
        else:
            kept.append(poi)

    must: list[str] = []
    missing: list[str] = []
    for name in prefs.mustVisit:
        hit = next((p for p in kept if _matches(name, p)), None)
        if hit is None:
            # 暂停开放的另外说明，不算"不在景点库里"
            if not any(_matches(name, p) for p in library if is_closed(p)):
                missing.append(name)
        elif hit.id not in must:
            must.append(hit.id)

    kept.sort(key=lambda p: (p.id not in must, -len(matched_interests(p, prefs.interests))))
    return Candidates(
        pois={p.id: p for p in kept}, must_visit=must, not_in_library=missing,
        avoided=avoided,
        closed_requested=closed_requested,
    )


def distance_km(a: PoiFile, b: PoiFile) -> float:
    """两点直线距离（公里）。只给模型做参考，真实交通时间由程序向高德查。"""
    assert a.location and a.location.value and b.location and b.location.value
    la1, lo1 = math.radians(a.location.value.lat), math.radians(a.location.value.lng)
    la2, lo2 = math.radians(b.location.value.lat), math.radians(b.location.value.lng)
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _hours_for_model(poi: PoiFile) -> Any:
    fact = poi.openingHours
    if fact is None or fact.verification == "todo" or fact.value is None:
        return "未知"
    h = fact.value
    if h.allDay:
        return "全天开放"
    return {
        "periods": [p.model_dump(exclude_none=True) for p in h.periods],
        "closedWeekdays": h.closedWeekdays,
        "note": h.note,
    }


def candidate_brief(c: Candidates, prefs: TravelerPreferences) -> list[dict[str, Any]]:
    """给模型看的候选清单。只放排行程要用的结构化信息。"""
    out = []
    for poi in c.pois.values():
        dur = poi.recommendedDurationMinutes
        out.append(
            {
                "id": poi.id,
                "name": poi.name,
                "district": poi.district,
                "category": poi.category,
                "fitsInterests": poi_interests(poi),
                "matchesUser": matched_interests(poi, prefs.interests),
                "mustVisit": poi.id in c.must_visit,
                "openingHours": _hours_for_model(poi),
                "recommendedDurationMinutes": dur.value if dur and dur.verification != "todo" else "未知",
            }
        )
    return out


def distance_table(c: Candidates) -> list[str]:
    """候选两两之间的直线距离，例如 "a—b 3.2km"。"""
    pois = list(c.pois.values())
    rows = []
    for i, a in enumerate(pois):
        for b in pois[i + 1 :]:
            rows.append(f"{a.id}—{b.id} {distance_km(a, b):.1f}km")
    return rows
