"""批量评测：读 eval/requests.json 里的一组请求，每条交给千问和豆包各排一份，输出 CSV 和 Markdown 汇总（板块 6）。

用法（在 Mac 终端）：
    cd ~/WuhanMemory-project2 && corepack pnpm eval:run --dry-run     # 只数要调用多少次，不调用模型
    cd ~/WuhanMemory-project2 && corepack pnpm eval:run               # 真实调用
    cd ~/WuhanMemory-project2 && corepack pnpm eval:run --only r01,r02 --repeat 2

和 /compare 页面走同一条路（ModelComparer）：偏好用文件里手写的，不让模型抽；两个模型同时排同一种侧重。
每次对比存进网站的 SQLite（model_comparisons，带请求 id），在 /compare 的历次对比里能点开看；
每次模型调用照常记在 llm_calls。路线先查 SQLite 缓存，缓存里没有的会调用高德，所以先跑 routes:prewarm。

输出 eval/results/<日期>.csv 和 eval/results/<日期>.md（同一天跑第二次是 <日期>-2）。
所有数字都是这次跑出来的，不写死、不预估；汇总只列数字和局限，不写"哪个模型更好"。
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.schemas.comparison import ModelComparison, SideResult
from app.schemas.planning import TravelerPreferences
from app.services.planning.compare_runner import DEFAULT_PROVIDERS, ModelComparer
from app.services.planning.emphasis import EMPHASES
from app.services.planning.model_compare import ModelSummary, error_label, summarize

REPO_ROOT = Path(__file__).resolve().parents[4]
REQUESTS_PATH = REPO_ROOT / "eval" / "requests.json"
RESULTS_DIR = REPO_ROOT / "eval" / "results"


class EvalRequest(BaseModel):
    id: str
    text: str
    preferences: TravelerPreferences
    emphasis: str
    covers: str = ""


def load_requests(path: Path) -> list[EvalRequest]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        items = [EvalRequest.model_validate(r) for r in raw["requests"]]
    except (KeyError, ValidationError) as exc:
        raise ValueError(f"{path} 的格式不对：{exc}") from exc
    seen: set[str] = set()
    for r in items:
        if r.id in seen:
            raise ValueError(f"请求 id 重复：{r.id}")
        seen.add(r.id)
        if r.emphasis not in EMPHASES:
            raise ValueError(f"{r.id} 的侧重不对：{r.emphasis}（只能是 {'、'.join(EMPHASES)}）")
        if r.preferences.days is None:
            raise ValueError(f"{r.id} 的偏好里没有天数")
    return items


@dataclass(frozen=True)
class CallPlan:
    comparisons: int
    min_calls: int
    max_calls: int


def call_plan(requests: int, repeat: int, models: int = len(DEFAULT_PROVIDERS)) -> CallPlan:
    """每次对比每个模型：排行程 1 次，有错误再修正 1 次。偏好是手写的，不抽。重试和重答另算，跑完在 CSV 里如实写。"""
    n = requests * repeat
    return CallPlan(comparisons=n, min_calls=n * models, max_calls=n * models * 2)


# ---------- 跑 ----------


@dataclass
class EvalRun:
    request: EvalRequest
    repeat_no: int
    comparison: ModelComparison


async def run_eval(
    comparer: ModelComparer, requests: Sequence[EvalRequest], repeat: int, out: Callable[[str], None] = print
) -> list[EvalRun]:
    runs: list[EvalRun] = []
    for r in requests:
        for k in range(1, repeat + 1):
            cmp = await comparer.compare(r.text, prefs=r.preferences, emphasis=r.emphasis, eval_request_id=r.id)
            runs.append(EvalRun(request=r, repeat_no=k, comparison=cmp))
            out(_line(r, k, cmp))
    return runs


def _side_short(s: SideResult) -> str:
    if s.quality is None:
        return f"{s.providerLabel} 没排出来（{s.error}）"
    q = s.quality
    return (
        f"{s.providerLabel} 第一版 {'通过' if q.firstPassed else f'{q.firstErrorCount} 错'}"
        f"{'，修正后' + ('通过' if q.finalPassed else '未通过') if q.repaired else ''}"
        f"，{s.calls.modelMs / 1000:.1f}s"
    )


def _line(r: EvalRequest, k: int, cmp: ModelComparison) -> str:
    return f"{r.id}#{k} · " + " · ".join(_side_short(s) for s in cmp.sides)


# ---------- CSV ----------

CSV_COLUMNS = [
    "request_id", "repeat", "emphasis", "request", "provider", "model", "error",
    "first_passed", "first_errors", "first_warnings", "first_error_codes", "repaired",
    "final_passed", "final_errors", "final_warnings", "final_error_codes",
    "fabricated_pois", "off_list_pois", "stops", "transport_minutes", "unknown_legs", "walking_meters", "day_ends",
    "model_seconds", "wall_seconds", "calls", "requests_sent", "retried_calls", "reasked_calls",
    "input_tokens", "output_tokens", "comparison_id",
]


def _codes(codes: dict[str, int]) -> str:
    return ";".join(f"{c}x{n}" for c, n in sorted(codes.items()))


def csv_rows(runs: Sequence[EvalRun]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in runs:
        for s in run.comparison.sides:
            q, p = s.quality, s.plan
            rows.append({
                "request_id": run.request.id,
                "repeat": run.repeat_no,
                "emphasis": run.request.emphasis,
                "request": run.request.text,
                "provider": s.provider,
                # 没排出来的一边对方没回答过，不知道真实模型名（见 model_compare.side_result）
                "model": (s.model or "") if q is not None else "",
                "error": s.error or "",
                "first_passed": "" if q is None else int(q.firstPassed),
                "first_errors": "" if q is None else q.firstErrorCount,
                "first_warnings": "" if q is None else q.firstWarningCount,
                "first_error_codes": "" if q is None else _codes(q.firstErrorCodes),
                "repaired": "" if q is None else int(q.repaired),
                "final_passed": "" if q is None else int(q.finalPassed),
                "final_errors": "" if q is None else q.finalErrorCount,
                "final_warnings": "" if q is None else q.finalWarningCount,
                "final_error_codes": "" if q is None else _codes(q.finalErrorCodes),
                "fabricated_pois": "" if q is None else ";".join(q.firstFabricatedPoiIds),
                "off_list_pois": "" if q is None else ";".join(q.firstOffListPoiIds),
                "stops": "" if p is None else p.stopCount,
                "transport_minutes": "" if p is None else p.transportMinutes,
                "unknown_legs": "" if p is None else p.unknownLegs,
                "walking_meters": "" if p is None else p.walkingMeters,
                "day_ends": "" if p is None else ";".join(d.end or "-" for d in p.days),
                "model_seconds": f"{s.calls.modelMs / 1000:.1f}",
                "wall_seconds": f"{s.wallMs / 1000:.1f}",
                "calls": s.calls.callCount,
                "requests_sent": s.calls.requestCount,
                "retried_calls": s.calls.retriedCalls,
                "reasked_calls": s.calls.reaskedCalls,
                "input_tokens": "" if s.calls.inputTokens is None else s.calls.inputTokens,
                "output_tokens": "" if s.calls.outputTokens is None else s.calls.outputTokens,
                "comparison_id": run.comparison.id,
            })
    return rows


def render_csv(runs: Sequence[EvalRun]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(csv_rows(runs))
    return buf.getvalue()


# ---------- Markdown 汇总 ----------


@dataclass(frozen=True)
class DataFacts:
    """景点库的情况，跑的时候现查（写进局限）。"""

    pois: int
    open_pois: int
    facts: int
    onsite: int
    confirmed: int
    placeholder: int
    todo: int
    expired: int


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.0f}%"


def _num(x: float | None, digits: int = 1, unit: str = "") -> str:
    return "—" if x is None else f"{x:.{digits}f}{unit}"


def _top(m: ModelSummary, k: int = 3) -> str:
    if not m.top_error_codes:
        return "没有错误"
    return "；".join(f"{error_label(c)}（{c}）{n} 次" for c, n in m.top_error_codes[:k])


def render_summary(runs: Sequence[EvalRun], *, run_date: date, repeat: int, facts: DataFacts,
                   csv_name: str, providers: Sequence[str] = DEFAULT_PROVIDERS) -> str:
    sides = [s for r in runs for s in r.comparison.sides]
    sides = [s if s.quality is not None else s.model_copy(update={"model": None}) for s in sides]
    summaries = [summarize(sides, p) for p in providers]
    request_ids = sorted({r.request.id for r in runs})
    lines = [
        f"# 双模型评测汇总（{run_date.isoformat()}）",
        "",
        f"由 `corepack pnpm eval:run` 生成，每个数字都是这次运行算出来的；逐条结果在 `{csv_name}`。",
        f"请求 {len(request_ids)} 条（`eval/requests.json`），每条每个模型跑 {repeat} 次，共 {len(runs)} 次对比。"
        "两个模型用同一份手写的偏好、同一份候选景点、同一种侧重，同时调用；差别只有模型。",
        "",
        "模型名：" + "；".join(f"{m.label} {('、'.join(m.models) or '不详')}" for m in summaries),
        "",
        "## 每个模型",
        "",
        "| 指标 | " + " | ".join(m.label for m in summaries) + " |",
        "|---|" + "---|" * len(summaries),
    ]

    def row(label: str, cells: list[str]) -> None:
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    row("跑了几次", [str(m.runs) for m in summaries])
    row("模型出错（没排出来）", [str(m.model_errors) for m in summaries])
    row("首次通过率（第一版没有错误）", [f"{_pct(m.first_pass_rate)}（{m.first_passed}/{m.runs}）" for m in summaries])
    row("修正后通过率", [f"{_pct(m.final_pass_rate)}（{m.final_passed}/{m.runs}）" for m in summaries])
    row("第一版平均错误数", [_num(m.avg_first_errors) for m in summaries])
    row("最常见的错误类型（第一版）", [_top(m) for m in summaries])
    row("第一版用了编造景点的次数", [str(m.fabricated_runs) for m in summaries])
    row("第一版用了候选以外景点的次数", [str(m.off_list_runs) for m in summaries])
    row("平均模型耗时", [_num(m.avg_model_seconds, unit=" 秒") for m in summaries])
    row("平均整体耗时（含查交通）", [_num(m.avg_wall_seconds, unit=" 秒") for m in summaries])
    row("平均 token（输入 / 输出）", [f"{_num(m.avg_input_tokens, 0)} / {_num(m.avg_output_tokens, 0)}" for m in summaries])
    lines += [
        "",
        "通过率的分母是全部运行次数，模型出错的也算在里面。错误数、耗时和 token 按排出来的运行平均。",
        "\"通过\"指校验没有错误；警告不算，因为景点资料还没实地核实，几乎每份行程都有警告。",
        "",
        "## 每条请求",
        "",
        "| 请求 | 侧重 | " + " | ".join(m.label for m in summaries) + " |",
        "|---|---|" + "---|" * len(summaries),
    ]
    for run in runs:
        cells = []
        for s in run.comparison.sides:
            if s.quality is None:
                cells.append(f"没排出来：{s.error}")
                continue
            q = s.quality
            first = "第一版通过" if q.firstPassed else f"第一版 {q.firstErrorCount} 错（{'、'.join(error_label(c) for c in q.firstErrorCodes)}）"
            final = "" if not q.repaired else ("，修正后通过" if q.finalPassed else f"，修正后仍有 {q.finalErrorCount} 错")
            cells.append(first + final)
        tag = run.request.id + (f"#{run.repeat_no}" if repeat > 1 else "")
        lines.append(f"| {tag} | {EMPHASES[run.request.emphasis].label} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## 局限",
        "",
        f"- 请求只有 {len(request_ids)} 条，每条每个模型跑 {repeat} 次。模型每次回答会有出入，这么少的样本只能看个大概，"
        "百分比相差一两条请求就会变很多。",
        f"- 景点库只有 {facts.pois} 个景点，能排进行程的 {facts.open_pois} 个。候选少，两个模型能做的选择本来就不多，"
        "多数行程会用到差不多的景点。",
        f"- 景点资料 {facts.facts} 条：实地核实 {facts.onsite}，核对过来源 {facts.confirmed}，占位 {facts.placeholder}，"
        f"TODO {facts.todo}，已过期 {facts.expired}。校验是对着这些资料做的：资料本身不对，校验结论也跟着不对。"
        "\"核对过来源\"里有不少来源程序打不开、没核对过原文（见 `docs/progress/current-progress.md`）。",
        "- 指标只看程序能检查的东西（景点存不存在、开放时间、交通时间、侧重的规则），看不出行程好不好玩、理由写得好不好。"
        "没有让一个模型给另一个打分。",
        "- 请求由 Cecilia 和 Claude 一起写，覆盖面有限；日期写死在 2026 年 11、12 月，闭馆日按资料里的星期算，没有节假日日历。",
        "- 交通时间用的是 SQLite 里的高德缓存（查询时间各不相同），两个模型用的是同一份缓存。",
        "- 不同时间跑的结果之间，链路可能改过（例如板块 6C 起钟点由程序推，\"交通时间不够\"不会再出现），"
        "比较之前先看 `docs/progress/current-progress.md` 里那段时间改了什么。",
        "",
        "这份汇总不下\"哪个模型更好\"的结论。",
        "",
    ]
    return "\n".join(lines)


def output_paths(results_dir: Path, run_date: date) -> tuple[Path, Path]:
    stem = run_date.isoformat()
    n = 1
    while True:
        name = stem if n == 1 else f"{stem}-{n}"
        csv_path, md_path = results_dir / f"{name}.csv", results_dir / f"{name}.md"
        if not csv_path.exists() and not md_path.exists():
            return csv_path, md_path
        n += 1


def data_facts(data_dir: Path, today: date, library: Sequence[object]) -> DataFacts:
    from app.data_quality.checker import check_data_dir

    s = check_data_dir(data_dir, today).stats
    open_pois = sum(
        1 for p in library
        if not (getattr(p, "operatingStatus", None) and p.operatingStatus.value  # type: ignore[attr-defined]
                and p.operatingStatus.value.code == "closed-temporarily")  # type: ignore[attr-defined]
    )
    return DataFacts(pois=s.pois, open_pois=open_pois, facts=s.facts, onsite=s.onsite, confirmed=s.confirmed,
                     placeholder=s.placeholder, todo=s.todo, expired=s.expired)


# ---------- 命令行 ----------


def rerender(csv_path: Path, requests: Sequence[EvalRequest], comparisons: object, facts: DataFacts) -> tuple[str, str]:
    """按 CSV 里记的对比 id，从 SQLite 取出存好的对比，重新生成 CSV 和汇总。不调用模型，数字都是当时跑出来存下的。
    用在改了输出格式或修了输出里的问题之后（2026-11-15：模型出错那一边的模型名）。"""
    by_id = {r.id: r for r in requests}
    rows = list(csv.DictReader(io.StringIO(csv_path.read_text(encoding="utf-8"))))
    runs: list[EvalRun] = []
    seen: set[str] = set()
    for row in rows:
        cid = row["comparison_id"]
        if cid in seen:
            continue
        seen.add(cid)
        cmp = comparisons.get(cid)  # type: ignore[attr-defined]
        if cmp is None:
            raise ValueError(f"数据库里没有对比 {cid}，没法重新生成")
        runs.append(EvalRun(request=by_id[row["request_id"]], repeat_no=int(row["repeat"]), comparison=cmp))
    repeat = max(r.repeat_no for r in runs)
    run_date = date.fromisoformat(csv_path.stem[:10])
    return render_csv(runs), render_summary(runs, run_date=run_date, repeat=repeat, facts=facts, csv_name=csv_path.name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="双模型批量评测（真实调用千问和豆包）")
    parser.add_argument("--dry-run", action="store_true", help="只检查请求文件、数要调用多少次，不调用模型")
    parser.add_argument("--repeat", type=int, default=1, help="每条请求每个模型跑几次，默认 1")
    parser.add_argument("--only", default="", help="只跑这几条，用逗号分开，例如 r01,r02")
    parser.add_argument("--requests", type=Path, default=REQUESTS_PATH)
    parser.add_argument("--rerender", type=Path, default=None,
                        help="不调用模型：按这个 CSV 里的对比 id 从数据库取出存好的结果，重新生成这一对 CSV 和汇总")
    if argv is None:
        argv = sys.argv[1:]
    argv = [a for a in argv if a != "--"]  # 有的 pnpm 版本会把 "--" 原样传进来
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat 至少是 1")

    requests = load_requests(args.requests)
    if args.rerender is not None:
        from app.core.config import settings
        from app.data_quality.rules import today_in_city
        from app.repositories.model_comparison_repository import SqliteModelComparisonRepository
        from app.repositories.poi_repository import SqlitePoiRepository

        csv_path = args.rerender if args.rerender.is_absolute() else (REPO_ROOT / args.rerender)
        facts = data_facts(settings.data_dir, today_in_city(), SqlitePoiRepository(settings.database_path).list_pois())
        new_csv, new_md = rerender(csv_path, requests, SqliteModelComparisonRepository(settings.database_path), facts)
        csv_path.write_text(new_csv, encoding="utf-8")
        csv_path.with_suffix(".md").write_text(new_md, encoding="utf-8")
        print(f"重新生成了：{csv_path.relative_to(REPO_ROOT)}、{csv_path.with_suffix('.md').relative_to(REPO_ROOT)}（没有调用模型）")
        return 0
    if args.only:
        wanted = [x.strip() for x in args.only.split(",") if x.strip()]
        unknown = [w for w in wanted if w not in {r.id for r in requests}]
        if unknown:
            parser.error(f"没有这些请求：{'、'.join(unknown)}")
        requests = [r for r in requests if r.id in wanted]

    plan = call_plan(len(requests), args.repeat)
    print(f"请求 {len(requests)} 条 × 每个模型 {args.repeat} 次 = {plan.comparisons} 次对比")
    print(f"模型调用：{plan.min_calls} 到 {plan.max_calls} 次（{'、'.join(DEFAULT_PROVIDERS)} 各排行程 1 次，有错误再修正 1 次；"
          "限流、出错时的重试和输出不合格时的重答另算，跑完写在 CSV 里）")
    if args.dry_run:
        print("--dry-run：没有调用模型。")
        return 0

    import asyncio

    import httpx

    from app.core.config import settings
    from app.data_quality.rules import today_in_city
    from app.repositories.conversation_repository import SqliteConversationRepository
    from app.repositories.itinerary_repository import SqliteItineraryRepository
    from app.repositories.model_comparison_repository import SqliteModelComparisonRepository
    from app.repositories.planning_round_repository import SqlitePlanningRoundRepository
    from app.repositories.poi_repository import SqlitePoiRepository
    from app.repositories.route_cache_repository import SqliteRouteCacheRepository
    from app.services.llm.factory import get_llm_gateway
    from app.services.planning.pipeline import PlanningPipeline
    from app.services.routing.amap import AmapRouteProvider
    from app.services.routing.service import RouteService

    gateway = get_llm_gateway()
    missing = [p.id for p in gateway.providers() if p.id in DEFAULT_PROVIDERS and not p.configured]
    if missing:
        print(f"这些模型还没配置：{'、'.join(missing)}（apps/api/.env）")
        return 1

    async def go() -> tuple[list[EvalRun], list[object]]:
        async with httpx.AsyncClient() as client:
            pois = SqlitePoiRepository(settings.database_path)
            routes = RouteService(pois, AmapRouteProvider(settings.amap_web_service_key, settings.amap_base_url, client),
                                  SqliteRouteCacheRepository(settings.database_path))
            pipeline = PlanningPipeline(
                gateway=gateway, pois=pois, routes=routes,
                itineraries=SqliteItineraryRepository(settings.database_path),
                conversations=SqliteConversationRepository(settings.database_path),
                rounds=SqlitePlanningRoundRepository(settings.database_path),
                today=today_in_city,
            )
            comparer = ModelComparer(pipeline, SqliteModelComparisonRepository(settings.database_path))
            return await run_eval(comparer, requests, args.repeat), list(pois.list_pois())

    runs, library = asyncio.run(go())
    today = today_in_city()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = output_paths(RESULTS_DIR, today)
    csv_path.write_text(render_csv(runs), encoding="utf-8")
    md_path.write_text(
        render_summary(runs, run_date=today, repeat=args.repeat, facts=data_facts(settings.data_dir, today, library),
                       csv_name=csv_path.name),
        encoding="utf-8",
    )
    print("")
    print(f"写好了：{csv_path.relative_to(REPO_ROOT)}、{md_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
