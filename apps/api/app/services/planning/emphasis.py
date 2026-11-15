"""三种侧重：同一个请求排三份方案，每份的候选、节奏和额外规则由程序先定好，再交给模型排（板块 5B）。

为什么由程序定：只在提示词里说"排得不一样"，模型常常排出几乎一样的三份；而且"不一样"说不清、查不了。
这里每种侧重都写成程序能检查的规则，不满足就算校验错误，交给模型修正一次。

规则（2026-11-15 Cecilia 定，数值是初值）：
- 经典必去：开放的景点全部做候选，带"5A"标签的排前面；5A 景点都必须排进去（用户说不去的除外）。
- 轻松少走路：节奏按"轻松"（每天最长 8 小时）；每天最多 3 站；每天 17:30 前离开最后一站；
  每天站与站之间步行加起来不超过 2 公里（含公交地铁换乘、进出站的步行）；步行超过 10 分钟就改公交地铁或打车。
- 深度文化：候选只给有文化类标签的景点；每站停留不少于建议游玩时长。
- 三份共用用户说的天数、日期、必去、不去；暂停开放的景点不进候选（select_candidates 已经去掉）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from app.schemas.planning import PlanDraft, TripFrame, ValidationIssue, ValidationReport
from app.schemas.poi import PoiFile
from app.schemas.route import RouteOut
from app.services.planning.candidates import Candidates
from app.services.planning.validate import fmt, parse_hhmm

EmphasisId = Literal["classic", "relaxed", "culture"]

FIVE_A_TAG = "5A"
CULTURE_TAGS = ("历史", "文物", "近代建筑", "民国建筑", "欧式建筑", "历史街区", "老街")
RELAXED_MAX_STOPS = 3
RELAXED_LATEST_END = 17 * 60 + 30
RELAXED_WALK_METERS = 2000
RELAXED_WALK_MAX_MINUTES = 10


@dataclass(frozen=True)
class Emphasis:
    id: EmphasisId
    label: str
    # 给模型看的这份方案的要求
    prompt: str


EMPHASES: dict[str, Emphasis] = {
    "classic": Emphasis(
        id="classic",
        label="经典必去",
        prompt=(
            "这份方案的侧重是「经典必去」：第一次来武汉最该看的地方。标了 mustVisit 的景点（包括 5A 景点）一个都不能少，"
            "其余按顺路程度补充。"
        ),
    ),
    "relaxed": Emphasis(
        id="relaxed",
        label="轻松少走路",
        prompt=(
            f"这份方案的侧重是「轻松少走路」：每天最多 {RELAXED_MAX_STOPS} 站；每天 {fmt(RELAXED_LATEST_END)} 之前离开最后一站；"
            f"同一天的景点要挨得近，站与站之间步行加起来不超过 {RELAXED_WALK_METERS // 1000} 公里（程序会用高德查，含地铁换乘和进出站的步行）；"
            "宁可少去一个地方，也要每站多待一会儿（stayMinutes 给足）。"
        ),
    ),
    "culture": Emphasis(
        id="culture",
        label="深度文化",
        prompt=(
            "这份方案的侧重是「深度文化」：候选只有历史文化类的景点。每个景点停留时间不能少于它的 recommendedDurationMinutes"
            "（写\"未知\"的按景点类型估计，宁长勿短）；可以少排几站，把时间留给看得细。"
        ),
    ),
}


def _has_tag(poi: PoiFile, tags: Sequence[str]) -> bool:
    return any(t in tags for t in poi.tags)


def candidates_for(emphasis: Emphasis, base: Candidates, library: Sequence[PoiFile]) -> Candidates:
    """在用户共用的候选（已去掉暂停开放和用户不去的）上，按侧重调整。不改 base。"""
    del library  # 预留：以后侧重可能要从全库里补候选
    if emphasis.id == "classic":
        five_a = [pid for pid, poi in base.pois.items() if FIVE_A_TAG in poi.tags]
        must = list(base.must_visit) + [pid for pid in five_a if pid not in base.must_visit]
        order = sorted(base.pois, key=lambda pid: (pid not in base.must_visit, pid not in five_a))
        return replace(base, pois={pid: base.pois[pid] for pid in order}, must_visit=must)
    if emphasis.id == "culture":
        kept = {pid: poi for pid, poi in base.pois.items() if pid in base.must_visit or _has_tag(poi, CULTURE_TAGS)}
        return replace(base, pois=kept, must_visit=list(base.must_visit))
    return replace(base, pois=dict(base.pois), must_visit=list(base.must_visit))


def emphasis_frame(emphasis: Emphasis, frame: TripFrame) -> TripFrame:
    if emphasis.id == "relaxed":
        return frame.model_copy(update={"pace": "relaxed"})
    return frame


def walk_limit(emphasis: Emphasis) -> int | None:
    """步行超过多少分钟就改坐车；None 表示用默认规则（transport.choose_leg 里的 15 分钟，尽量走路时 30 分钟）。"""
    return RELAXED_WALK_MAX_MINUTES if emphasis.id == "relaxed" else None


def _walking(route: RouteOut | None) -> int | None:
    if route is None or route.status != "ok":
        return None
    if route.mode == "walk":
        return route.walkingDistanceMeters if route.walkingDistanceMeters is not None else route.distanceMeters
    if route.mode == "transit":
        return route.walkingDistanceMeters
    return 0


def check_emphasis(
    emphasis: Emphasis,
    draft: PlanDraft,
    *,
    candidates: Candidates,
    legs: Mapping[tuple[str, str], RouteOut | None],
    frame: TripFrame,
) -> list[ValidationIssue]:
    """侧重的额外规则。不满足的是错误（交给模型修正）；没法判断的是警告。通用的规则在 validate_itinerary 里。"""
    del frame  # 轻松的节奏上限由 emphasis_frame 改了 frame，validate_itinerary 会按它查
    tag = f"（{emphasis.label}）"
    out: list[ValidationIssue] = []
    pois = candidates.pois

    def err(code: str, message: str, **kw: object) -> None:
        out.append(ValidationIssue(level="error", code=code, message=tag + message, **kw))  # type: ignore[arg-type]

    def warn(code: str, message: str, **kw: object) -> None:
        out.append(ValidationIssue(level="warning", code=code, message=tag + message, **kw))  # type: ignore[arg-type]

    if emphasis.id == "classic":
        used = {s.poiId for d in draft.days for s in d.stops}
        for pid in candidates.must_visit:
            poi = pois.get(pid)
            if poi is not None and FIVE_A_TAG in poi.tags and pid not in used:
                err("emphasis-must-5a", f"5A 景点{poi.name}没有排进去，这份方案要求 5A 景点都去。", poiId=pid)

    elif emphasis.id == "relaxed":
        for day in draft.days:
            d = day.dayNumber
            if len(day.stops) > RELAXED_MAX_STOPS:
                err("emphasis-too-many-stops", f"第 {d} 天排了 {len(day.stops)} 站，这份方案每天最多 {RELAXED_MAX_STOPS} 站。", dayNumber=d)
            leaves = [t for t in (parse_hhmm(s.leave) for s in day.stops) if t is not None]
            if leaves and max(leaves) > RELAXED_LATEST_END:
                err(
                    "emphasis-ends-late",
                    f"第 {d} 天 {fmt(max(leaves))} 才离开最后一站，这份方案要在 {fmt(RELAXED_LATEST_END)} 之前结束。",
                    dayNumber=d,
                )
            total = 0
            unknown = 0
            for a, b in zip(day.stops, day.stops[1:]):
                if a.poiId not in pois or b.poiId not in pois or a.poiId == b.poiId:
                    continue  # 景点不存在、重复，validate_itinerary 已经报过
                w = _walking(legs.get((a.poiId, b.poiId)))
                if w is None:
                    unknown += 1
                else:
                    total += w
            if total > RELAXED_WALK_METERS:
                err(
                    "emphasis-walk-too-far",
                    f"第 {d} 天站与站之间要走 {total} 米（含地铁换乘和进出站），这份方案每天不超过 {RELAXED_WALK_METERS} 米。",
                    dayNumber=d,
                )
            elif unknown:
                warn(
                    "emphasis-walk-unknown",
                    f"第 {d} 天有 {unknown} 段不知道要走多远，没法确认步行在 {RELAXED_WALK_METERS} 米以内（已知的 {total} 米）。",
                    dayNumber=d,
                )

    elif emphasis.id == "culture":
        for day in draft.days:
            for s in day.stops:
                poi = pois.get(s.poiId)
                if poi is None:
                    continue
                fact = poi.recommendedDurationMinutes
                rec = fact.value if fact is not None and fact.verification != "todo" else None
                a, b = parse_hhmm(s.arrive), parse_hhmm(s.leave)
                if rec is None or a is None or b is None or b <= a:
                    continue
                if b - a < rec:
                    err(
                        "emphasis-stay-short",
                        f"第 {day.dayNumber} 天{poi.name}只停留 {b - a} 分钟，这份方案每站不少于建议游玩的 {rec} 分钟。",
                        dayNumber=day.dayNumber,
                        poiId=s.poiId,
                    )
    return out


def merge_issues(report: ValidationReport, extra: list[ValidationIssue]) -> ValidationReport:
    issues = [*report.issues, *extra]
    errors = any(i.level == "error" for i in issues)
    status = "failed" if errors else ("warning" if issues else "passed")
    return ValidationReport(status=status, issues=issues)
