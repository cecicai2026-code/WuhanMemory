"""双模型并排对比的计算（板块 6）。全部是纯函数：不调用模型、不联网、不查数据库。

输入是两边各自保存下来的行程快照（ItineraryVersionData）和网关的调用记录，输出是每边的数字、
两份行程的差异、并排的对比表，以及批量评测的汇总。能用 5B 的就用 5B 的（plan_metrics、compare_plans、near_duplicate）。

规则（2026-11-15 Cecilia 确认）：
- "通过"指没有错误。警告不算：现在景点资料全是占位，任何行程都有警告。
- 编造的景点：id 在整个景点库里都找不到。在库里、但不在这次的候选里的（用户说不去、暂停开放、侧重没给），单独算"候选以外"。
- 耗时分"模型耗时"（这一边每次调用的耗时相加）和"整体耗时"（含查交通）。
- 汇总的通过率按全部请求算，模型出错的也在分母里，出错次数另外列出来。
- 只列数字，不写哪个模型更好。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from app.schemas.comparison import (
    CallStats,
    ComparisonTable,
    DayDiff,
    MovedPoi,
    PlanDiff,
    PoiRef,
    QualityMetrics,
    SideResult,
)
from app.schemas.itinerary import ComparisonRow, ItineraryVersionData
from app.schemas.planning import PlanDraft, ValidationReport
from app.services.llm.base import LLMCallRecord
from app.services.planning.metrics import compare_plans, near_duplicate, plan_metrics

# 错误 code 的中文名，对比表和汇总里用。新加了校验规则要在这里补上，没补的显示 code 本身。
ERROR_LABELS: dict[str, str] = {
    "unknown-poi": "不在候选里的景点",
    "poi-closed": "暂停开放的景点",
    "duplicate-poi": "同一景点排两次",
    "day-count": "天数不对",
    "day-number": "天的编号不对",
    "empty-day": "某天没有景点",
    "bad-time": "时间格式不对",
    "time-order": "离开不晚于到达",
    "closed-day": "闭馆日",
    "before-open": "开门前到达",
    "after-last-entry": "过了最晚入场",
    "after-close": "关门后才离开",
    "overlap": "时间重叠",
    "transport-too-short": "交通时间不够",
    "day-window": "超出 08:00 到 22:00",
    "day-too-long": "一天太长",
    "transport-unknown": "交通没查到，排不出时间",
    "day-overflow": "推到午夜还没排完",
    "emphasis-must-5a": "漏了 5A 景点（经典必去）",
    "emphasis-too-many-stops": "一天站数太多（轻松少走路）",
    "emphasis-ends-late": "结束太晚（轻松少走路）",
    "emphasis-walk-too-far": "步行太远（轻松少走路）",
    "emphasis-stay-short": "停留短于建议时长（深度文化）",
}


def error_label(code: str) -> str:
    return ERROR_LABELS.get(code, code)


# ---------- 调用记录 ----------


def call_stats(calls: Sequence[LLMCallRecord]) -> CallStats:
    known_in = [c.input_tokens for c in calls if c.input_tokens is not None]
    known_out = [c.output_tokens for c in calls if c.output_tokens is not None]
    return CallStats(
        callCount=len(calls),
        requestCount=sum(c.attempts for c in calls),
        failedCalls=sum(1 for c in calls if not c.ok),
        retriedCalls=sum(1 for c in calls if c.retried),
        reaskedCalls=sum(1 for c in calls if c.repaired),
        modelMs=sum(c.latency_ms for c in calls),
        inputTokens=sum(known_in) if known_in else None,
        outputTokens=sum(known_out) if known_out else None,
        tokensUnknownCalls=sum(1 for c in calls if c.input_tokens is None or c.output_tokens is None),
        byTask=dict(Counter(c.task for c in calls)),
    )


# ---------- 一份行程的校验情况 ----------


def _codes(report: ValidationReport) -> dict[str, int]:
    return dict(Counter(i.code for i in report.issues if i.level == "error"))


def _bad_pois(report: ValidationReport, draft: PlanDraft, library_ids: Collection[str]) -> tuple[list[str], list[str]]:
    """（编造的，候选以外的）。依据是校验报出的 unknown-poi，再对照整个景点库分开。按出现顺序，不重复。"""
    flagged = {i.poiId for i in report.issues if i.code == "unknown-poi" and i.poiId}
    fabricated: list[str] = []
    off_list: list[str] = []
    for day in draft.days:
        for s in day.stops:
            if s.poiId not in flagged:
                continue
            target = off_list if s.poiId in library_ids else fabricated
            if s.poiId not in target:
                target.append(s.poiId)
    return fabricated, off_list


def first_round(v: ItineraryVersionData) -> tuple[ValidationReport, PlanDraft]:
    """第一版的校验报告和模型输出。没修正过的版本，第一版就是最终版。"""
    if v.planner.rounds == 1:
        return v.firstValidation or v.validation, v.firstDraft or v.draft
    if v.firstValidation is None or v.firstDraft is None:
        raise ValueError("修正过的版本缺第一版的校验报告，算不出第一版的数字")
    return v.firstValidation, v.firstDraft


def quality_metrics(v: ItineraryVersionData, library_ids: Collection[str]) -> QualityMetrics:
    first, first_draft = first_round(v)
    final = v.validation
    ff, fo = _bad_pois(first, first_draft, library_ids)
    lf, lo = _bad_pois(final, v.draft, library_ids)
    return QualityMetrics(
        firstPassed=not first.errors,
        firstStatus=first.status,
        firstErrorCount=len(first.errors),
        firstWarningCount=len(first.warnings),
        firstErrorCodes=_codes(first),
        repaired=v.planner.rounds == 2,
        finalPassed=not final.errors,
        finalStatus=final.status,
        finalErrorCount=len(final.errors),
        finalWarningCount=len(final.warnings),
        finalErrorCodes=_codes(final),
        firstFabricatedPoiIds=ff,
        firstOffListPoiIds=fo,
        finalFabricatedPoiIds=lf,
        finalOffListPoiIds=lo,
    )


def side_result(
    *,
    provider: str,
    provider_label: str,
    calls: Sequence[LLMCallRecord],
    wall_ms: int,
    library_ids: Collection[str],
    version: ItineraryVersionData | None = None,
    version_id: str | None = None,
    error: str | None = None,
) -> SideResult:
    if version is None:
        return SideResult(
            provider=provider,
            providerLabel=provider_label,
            # 只取对方真的回答了的调用里的模型名。失败的调用里记的是配置里的模型设置，
            # 豆包那是推理接入点 ID（ep- 开头），不能给前端，也不能写进评测结果
            model=next((c.model for c in calls if c.ok and c.model), None),
            error=error or "没有排出行程",
            calls=call_stats(calls),
            wallMs=wall_ms,
        )
    return SideResult(
        provider=provider,
        providerLabel=provider_label,
        model=version.planner.model,
        versionId=version_id,
        quality=quality_metrics(version, library_ids),
        plan=version.metrics or plan_metrics(version),
        calls=call_stats(calls),
        wallMs=wall_ms,
    )


# ---------- 两份行程的差异 ----------


def _refs(v: ItineraryVersionData) -> list[PoiRef]:
    out: list[PoiRef] = []
    for d in v.days:
        for s in d.stops:
            if all(r.poiId != s.poiId for r in out):
                out.append(PoiRef(poiId=s.poiId, name=s.name))
    return out


def _day_of(v: ItineraryVersionData) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in v.days:
        for s in d.stops:
            out.setdefault(s.poiId, d.dayNumber)
    return out


def plan_diff(left: ItineraryVersionData, right: ItineraryVersionData) -> PlanDiff:
    """只看最终版里真实存在的景点（编造的景点不会出现在行程里，在校验情况里另算）。"""
    lr, rr = _refs(left), _refs(right)
    l_ids, r_ids = {r.poiId for r in lr}, {r.poiId for r in rr}
    l_day, r_day = _day_of(left), _day_of(right)

    days: list[DayDiff] = []
    for n in range(1, max(len(left.days), len(right.days)) + 1):
        ld = next((d for d in left.days if d.dayNumber == n), None)
        rd = next((d for d in right.days if d.dayNumber == n), None)
        lo = [PoiRef(poiId=s.poiId, name=s.name) for s in (ld.stops if ld else [])]
        ro = [PoiRef(poiId=s.poiId, name=s.name) for s in (rd.stops if rd else [])]
        r_set = {r.poiId for r in ro}
        common = [r for r in lo if r.poiId in r_set]
        same: bool | None = None
        if len(common) >= 2:
            order_r = [r.poiId for r in ro if r.poiId in {c.poiId for c in common}]
            same = [c.poiId for c in common] == order_r
        days.append(DayDiff(dayNumber=n, orders=[lo, ro], common=common, sameOrder=same))

    moved = [
        MovedPoi(poiId=r.poiId, name=r.name, days=[l_day[r.poiId], r_day[r.poiId]])
        for r in lr
        if r.poiId in r_ids and l_day[r.poiId] != r_day[r.poiId]
    ]
    return PlanDiff(
        onlyLeft=[r for r in lr if r.poiId not in r_ids],
        onlyRight=[r for r in rr if r.poiId not in l_ids],
        both=[r for r in lr if r.poiId in r_ids],
        days=days,
        moved=moved,
        nearDuplicate=near_duplicate(left.draft, right.draft),
    )


# ---------- 并排的对比表 ----------


def _seconds(ms: int) -> str:
    return f"{ms / 1000:.1f} 秒"


def _codes_text(codes: dict[str, int]) -> str:
    if not codes:
        return "—"
    return "、".join(f"{error_label(c)} ×{n}" for c, n in sorted(codes.items(), key=lambda kv: (-kv[1], kv[0])))


def _check_text(passed: bool, errors: int, warnings: int) -> str:
    return f"{'通过' if passed else '未通过'}：{errors} 条错误、{warnings} 条警告"


def _repair_text(q: QualityMetrics) -> str:
    if not q.repaired:
        return "没修正（第一版没有错误）" if q.firstPassed else "没修正"
    if q.finalPassed:
        return "修正一次后通过"
    return f"修正一次后仍未通过：还有 {q.finalErrorCount} 条错误"


def _ids_text(ids: list[str], names: dict[str, str]) -> str:
    if not ids:
        return "没有"
    return f"{len(ids)} 个：" + "、".join(names.get(i, f"「{i}」") for i in ids)


def _tokens_text(c: CallStats) -> str:
    if c.inputTokens is None and c.outputTokens is None:
        return "不详"
    text = f"输入 {c.inputTokens or 0}、输出 {c.outputTokens or 0}"
    if c.tokensUnknownCalls:
        text += f"（{c.tokensUnknownCalls} 次调用没返回）"
    return text


def _calls_text(c: CallStats) -> str:
    text = f"{c.callCount} 次调用，发了 {c.requestCount} 次请求"
    extra = []
    if c.retriedCalls:
        extra.append(f"{c.retriedCalls} 次调用重试过")
    if c.reaskedCalls:
        extra.append(f"{c.reaskedCalls} 次输出不合格让模型重答")
    if c.failedCalls:
        extra.append(f"{c.failedCalls} 次失败")
    return text + (f"（{'，'.join(extra)}）" if extra else "")


def comparison_table(
    sides: Sequence[SideResult],
    versions: Sequence[ItineraryVersionData | None],
    poi_names: dict[str, str],
) -> ComparisonTable:
    """质量的几行在前，5B 的行程数字在中间，耗时和调用在后。没排出来的一边写原因。"""
    labels = [s.providerLabel for s in sides]
    n = len(sides)

    def row(key: str, label: str, fn, value=None, note: str | None = None) -> ComparisonRow:  # type: ignore[no-untyped-def]
        texts, values = [], []
        for s in sides:
            if s.quality is None and key not in ("modelTime", "wallTime", "calls", "tokens"):
                texts.append(f"模型没排出来：{s.error}" if key == "firstCheck" else "—")
                values.append(None)
                continue
            texts.append(fn(s))
            values.append(value(s) if value else None)
        return ComparisonRow(key=key, label=label, texts=texts, values=values, note=note)

    rows = [
        row("firstCheck", "第一版校验", lambda s: _check_text(s.quality.firstPassed, s.quality.firstErrorCount, s.quality.firstWarningCount),
            lambda s: float(s.quality.firstErrorCount), note="通过指没有错误；资料还没核实，警告几乎免不了"),
        row("firstCodes", "第一版错误类型", lambda s: _codes_text(s.quality.firstErrorCodes)),
        row("repair", "修正", lambda s: _repair_text(s.quality)),
        row("fabricated", "编造的景点（第一版）", lambda s: _ids_text(s.quality.firstFabricatedPoiIds, poi_names),
            lambda s: float(len(s.quality.firstFabricatedPoiIds)), note="景点 id 在整个景点库里都找不到"),
        row("offList", "候选以外的景点（第一版）", lambda s: _ids_text(s.quality.firstOffListPoiIds, poi_names),
            lambda s: float(len(s.quality.firstOffListPoiIds)), note="在景点库里，但这次不能用：用户说不去、暂停开放或这种侧重没给"),
    ]

    shown = [(i, v) for i, v in enumerate(versions) if v is not None and sides[i].quality is not None]
    if shown:
        plan_table = compare_plans([labels[i] for i, _ in shown], [v for _, v in shown])
        for pr in plan_table.rows:
            if pr.key == "validation":
                pr = pr.model_copy(update={"label": "最终校验"})
            texts: list[str] = ["—"] * n
            values: list[float | None] = [None] * n
            for j, (i, _) in enumerate(shown):
                texts[i], values[i] = pr.texts[j], pr.values[j]
            rows.append(pr.model_copy(update={"texts": texts, "values": values}))

    rows += [
        row("modelTime", "模型耗时", lambda s: _seconds(s.calls.modelMs), lambda s: float(s.calls.modelMs),
            note="这一边每次模型调用的耗时相加；抽偏好两边共用，不算在内"),
        row("wallTime", "整体耗时", lambda s: _seconds(s.wallMs), lambda s: float(s.wallMs), note="含查交通和校验"),
        row("calls", "调用次数", lambda s: _calls_text(s.calls), lambda s: float(s.calls.callCount)),
        row("tokens", "token", lambda s: _tokens_text(s.calls)),
    ]
    return ComparisonTable(labels=labels, rows=rows)


# ---------- 批量评测的汇总 ----------


@dataclass(frozen=True)
class ModelSummary:
    provider: str
    label: str
    runs: int
    model_errors: int
    first_passed: int
    final_passed: int
    # 排出来的请求里，第一版平均几条错误
    avg_first_errors: float | None
    # 第一版错误类型，按出现次数从多到少
    top_error_codes: list[tuple[str, int]]
    fabricated_runs: int
    off_list_runs: int
    # 耗时和 token 按排出来的请求平均（模型出错的耗时多半是等到超时，不算进来）
    avg_model_seconds: float | None
    avg_wall_seconds: float | None
    avg_input_tokens: float | None
    avg_output_tokens: float | None
    models: list[str]

    @property
    def first_pass_rate(self) -> float | None:
        return self.first_passed / self.runs if self.runs else None

    @property
    def final_pass_rate(self) -> float | None:
        return self.final_passed / self.runs if self.runs else None


def _avg(xs: Sequence[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def summarize(sides: Sequence[SideResult], provider: str) -> ModelSummary:
    """一个模型在一组请求上的汇总。sides 里只取这个模型的。通过率的分母是全部请求（模型出错的也算）。"""
    mine = [s for s in sides if s.provider == provider]
    done = [s for s in mine if s.quality is not None]
    codes: Counter[str] = Counter()
    for s in done:
        codes.update(s.quality.firstErrorCodes)  # type: ignore[union-attr]
    return ModelSummary(
        provider=provider,
        label=mine[0].providerLabel if mine else provider,
        runs=len(mine),
        model_errors=len(mine) - len(done),
        first_passed=sum(1 for s in done if s.quality.firstPassed),  # type: ignore[union-attr]
        final_passed=sum(1 for s in done if s.quality.finalPassed),  # type: ignore[union-attr]
        avg_first_errors=_avg([float(s.quality.firstErrorCount) for s in done]),  # type: ignore[union-attr]
        top_error_codes=sorted(codes.items(), key=lambda kv: (-kv[1], kv[0])),
        fabricated_runs=sum(1 for s in done if s.quality.firstFabricatedPoiIds),  # type: ignore[union-attr]
        off_list_runs=sum(1 for s in done if s.quality.firstOffListPoiIds),  # type: ignore[union-attr]
        avg_model_seconds=_avg([s.calls.modelMs / 1000 for s in done]),
        avg_wall_seconds=_avg([s.wallMs / 1000 for s in done]),
        avg_input_tokens=_avg([float(s.calls.inputTokens) for s in done if s.calls.inputTokens is not None]),
        avg_output_tokens=_avg([float(s.calls.outputTokens) for s in done if s.calls.outputTokens is not None]),
        models=sorted({s.model for s in mine if s.model}),
    )
