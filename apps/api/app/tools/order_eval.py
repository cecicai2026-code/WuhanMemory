"""量一量"顺序由程序按真实交通时间重排"（ADR 0010）的效果。不调用模型，也不调用高德。

做法：
- 取开发数据库里存过的每个行程版本（地图工作台排的、模型对比和批量评测排的都算），拿出模型原样给的顺序：
  板块 6C 之后的版本有 outline；之前的版本用 draft（模型自己写了钟点）里的顺序、第一站到达时间和每站停留时长。
- 用现在的重排规则（app/services/planning/order.py）对每一天重排一次，和模型的顺序比路上的总分钟数。
- 交通时间只从 SQLite 里的高德路线缓存读（和规划时选交通方式的规则一样），缓存里缺了或过期了的那一天不算。
- 错误数用现在的景点资料、推钟点、validate_itinerary 和侧重规则算（规划时就是这样比的）。

用法（项目根目录）：
    corepack pnpm eval:order
结果写到 eval/results/route-order-<今天>.md 和 .csv，原样提交，不手改。
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.config import settings
from app.repositories.poi_repository import SqlitePoiRepository
from app.repositories.route_cache_repository import SqliteRouteCacheRepository
from app.schemas.itinerary import ItineraryVersionData
from app.schemas.planning import OutlineDay, OutlineStop, PlanDraft, PlanOutline
from app.schemas.route import RouteOut
from app.services.planning.candidates import select_candidates
from app.services.planning.emphasis import EMPHASES, candidates_for, check_emphasis, merge_issues, walk_limit
from app.services.planning.order import MAX_STOPS, optimize_day, pairs_needed
from app.services.planning.preferences import frame_for
from app.services.planning.schedule import schedule
from app.services.planning.transport import cached_leg
from app.services.planning.validate import parse_hhmm, validate_itinerary
from app.services.routing.service import RouteService

ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = ROOT / "eval" / "results"


class _NoNetwork:
    """只读缓存时用的假高德：被调用就说明代码走错了路。"""

    name = "cache-only"

    async def plan(self, *_: Any, **__: Any) -> Any:
        raise RuntimeError("order_eval 不调用高德")


@dataclass
class Row:
    version_id: str
    provider: str
    emphasis: str
    day: int
    stops: int
    model_minutes: int | None
    best_minutes: int | None
    changed: bool
    reason: str


def outline_of(data: ItineraryVersionData) -> PlanOutline | None:
    """模型原样给的顺序。6C 之前的版本从 draft 里还原（出发时间 = 第一站到达，停留 = 离开 - 到达）。"""
    if data.outline is not None:
        return data.outline
    return _from_draft(data.draft)


def _from_draft(draft: PlanDraft) -> PlanOutline | None:
    days = []
    for d in draft.days:
        stops = []
        for s in d.stops:
            a, b = parse_hhmm(s.arrive), parse_hhmm(s.leave)
            if a is None or b is None or b <= a:
                return None
            stops.append(OutlineStop(poiId=s.poiId, stayMinutes=b - a, reason=s.reason))
        start = d.stops[0].arrive if d.stops else "09:00"
        days.append(OutlineDay(dayNumber=d.dayNumber, theme=d.theme, start=start, stops=stops))
    return PlanOutline(title=draft.title, days=days)


def evaluate(db: Path) -> tuple[list[Row], Counter[str]]:
    pois_repo = SqlitePoiRepository(db)
    library = pois_repo.list_pois()
    service = RouteService(pois_repo, _NoNetwork(), SqliteRouteCacheRepository(db))  # type: ignore[arg-type]
    skipped: Counter[str] = Counter()
    rows: list[Row] = []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        records = con.execute("select id, provider, data_json from itinerary_versions order by created_at").fetchall()
    finally:
        con.close()
    for version_id, provider, raw in records:
        try:
            data = ItineraryVersionData.model_validate(json.loads(raw))
        except ValidationError:
            skipped["版本格式读不了"] += 1
            continue
        outline = outline_of(data)
        if outline is None:
            skipped["还原不出模型的顺序"] += 1
            continue
        if data.preferences.days is None:
            skipped["偏好里没有天数"] += 1
            continue
        emphasis = EMPHASES.get(data.emphasis or "")
        base = select_candidates(library, data.preferences)
        candidates = candidates_for(emphasis, base, library) if emphasis else base
        # 用候选以外的景点（编造的、或现在已经暂停开放的）的天，重排时按 invalid-stops 跳过
        known = set(candidates.pois)
        transport = frame_for(data.preferences).transport
        walk_max = walk_limit(emphasis) if emphasis else None
        frame = data.frame
        today: date = data.dataAsOf

        pair_routes: dict[tuple[str, str], RouteOut] = {}
        travel: dict[tuple[str, str], int | None] = {}
        for a, b in pairs_needed(outline, known):
            leg = cached_leg(service, a, b, transport, walk_max=walk_max)
            if leg is not None:
                pair_routes[(a, b)] = leg.route
            travel[(a, b)] = leg.route.durationMinutes if leg is not None else None

        def day_errors(o: PlanOutline, d: int) -> int:
            draft, timing = schedule(o, pois=candidates.pois, legs=pair_routes, frame=frame)
            report = validate_itinerary(draft, pois=candidates.pois, legs=pair_routes, frame=frame, today=today)
            extra = check_emphasis(emphasis, draft, candidates=candidates, legs=pair_routes, frame=frame) if emphasis else []
            return sum(1 for i in merge_issues(report, [*timing, *extra]).errors if i.dayNumber == d)

        for day in outline.days:
            if len(day.stops) < 2:
                continue
            _, note = optimize_day(outline, day.dayNumber, known=known, travel=travel, day_errors=day_errors)
            rows.append(Row(
                version_id=version_id, provider=provider, emphasis=data.emphasis or "", day=day.dayNumber,
                stops=len(day.stops), model_minutes=note.modelTransportMinutes, best_minutes=note.transportMinutes,
                changed=note.changed, reason=note.reason,
            ))
    return rows, skipped


def _pct(part: float, whole: float) -> str:
    return f"{part / whole * 100:.1f}%" if whole else "—"


def summary_markdown(rows: list[Row], skipped: Counter[str], when: date) -> str:
    measured = [r for r in rows if r.model_minutes is not None and r.best_minutes is not None]
    changed = [r for r in measured if r.changed]
    reasons = Counter(r.reason for r in rows)
    before = sum(r.model_minutes for r in measured)  # type: ignore[misc]
    after = sum(r.best_minutes for r in measured)  # type: ignore[misc]
    savings = sorted(((r.model_minutes - r.best_minutes) / r.model_minutes) for r in changed if r.model_minutes)  # type: ignore[operator]
    lines = [
        f"# 顺序重排的效果（{when.isoformat()}）",
        "",
        "由 `corepack pnpm eval:order` 生成，每个数字都是这次运行算出来的；逐天结果在同名 `.csv`。"
        "不调用模型，也不调用高德：交通时间只读 SQLite 里的高德路线缓存。",
        "",
        "对象：开发数据库里存过的每个行程版本，模型原样给的每一天（至少 2 站）。"
        "规则和规划时一样（ADR 0010）：只在同一天内部换顺序；第一站不固定；最小化相邻两站的交通分钟数之和；"
        "新顺序这一天的校验错误不能比模型的顺序多；分钟数一样时保留模型的顺序。",
        "",
        "## 汇总",
        "",
        "| 指标 | 数值 |",
        "|---|---|",
        f"| 至少 2 站的天 | {len(rows)} |",
        f"| 模型顺序的交通时间算得出来的天 | {len(measured)} |",
        f"| 程序换了顺序的天 | {len(changed)}（{_pct(len(changed), len(measured))}） |",
        f"| 这些天路上的分钟数合计：模型顺序 → 重排后 | {before} → {after}（少 {_pct(before - after, before)}） |",
    ]
    if savings:
        mid = savings[len(savings) // 2]
        lines.append(f"| 换了顺序的天，每天少的比例：中位数 / 最大 | {mid * 100:.1f}% / {savings[-1] * 100:.1f}% |")
    lines += ["", "## 每种结果的天数", "", "| 结果 | 天数 |", "|---|---|"]
    names = {
        "shorter": "换了更省路的顺序",
        "already-shortest": "模型的顺序已经最省",
        "more-errors": "更省路的顺序都会多出错误，保留",
        "travel-unknown": "缓存里缺交通时间，没比较",
        "invalid-stops": "有候选以外或重复的站，没比较",
        "too-many-stops": f"超过 {MAX_STOPS} 站，没穷举",
    }
    for k, n in reasons.most_common():
        lines.append(f"| {names.get(k, k)}（{k}） | {n} |")
    by_provider: dict[str, list[Row]] = {}
    for r in measured:
        by_provider.setdefault(r.provider, []).append(r)
    lines += ["", "## 按模型", "", "| 模型 | 天数 | 换了顺序 | 分钟数：模型顺序 → 重排后 |", "|---|---|---|---|"]
    for p, rs in sorted(by_provider.items()):
        b = sum(r.model_minutes for r in rs)  # type: ignore[misc]
        a = sum(r.best_minutes for r in rs)  # type: ignore[misc]
        lines.append(f"| {p} | {len(rs)} | {sum(r.changed for r in rs)} | {b} → {a}（少 {_pct(b - a, b)}） |")
    if skipped:
        lines += ["", "## 没算进来的版本", ""]
        lines += [f"- {k}：{n} 个" for k, n in skipped.items()]
    lines += [
        "",
        "## 局限",
        "",
        "- 行程是开发和评测时排出来的，同一个请求会有好几个版本，景点只有 10 个，所以样本小、彼此不独立。",
        "- 错误数用现在的景点资料和现在的规则算，和这些行程当时的校验结果可能不完全一样。",
        "- 交通时间是缓存里的高德结果，查询时间各不相同；打车的路线大多没缓存，那些天不算。",
        "- 只量了路上的分钟数，没量重排以后一天总时长（含等开门）的变化。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    today = date.today()
    rows, skipped = evaluate(settings.database_path)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = OUT_DIR / f"route-order-{today.isoformat()}"
    with open(stem.with_suffix(".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["version_id", "provider", "emphasis", "day", "stops", "model_minutes", "best_minutes", "changed", "reason"])
        for r in rows:
            w.writerow([r.version_id, r.provider, r.emphasis, r.day, r.stops,
                        "" if r.model_minutes is None else r.model_minutes,
                        "" if r.best_minutes is None else r.best_minutes, r.changed, r.reason])
    stem.with_suffix(".md").write_text(summary_markdown(rows, skipped, today), encoding="utf-8")
    print(f"写好了 {stem.with_suffix('.md')} 和 .csv（{len(rows)} 天）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
