"""双模型对比计算的测试（板块 6）。不调用模型、不联网。

景点名、id、耗时、token 都是虚构的测试值，不是真实景点信息，也不是真实的模型结果。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.itinerary import ItineraryVersionData
from app.schemas.planning import PlanDraft, ValidationReport
from app.services.llm.base import LLMCallRecord
from app.services.planning.model_compare import (
    call_stats,
    comparison_table,
    first_round,
    plan_diff,
    quality_metrics,
    side_result,
    summarize,
)
from tests.test_plan_metrics import draft, leg, stop, version

LIBRARY = {"a", "b", "c", "d", "e", "avoided"}


def call(task: str, ms: int, *, attempts: int = 1, ok: bool = True, retried: bool = False, repaired: bool = False,
         tin: int | None = 100, tout: int | None = 50, model: str | None = "test-model") -> LLMCallRecord:
    return LLMCallRecord(trace_id="t", task=task, provider="qwen", model=model, started_at="2026-11-15T00:00:00",
                         latency_ms=ms, attempts=attempts, retried=retried, repaired=repaired, ok=ok,
                         error_code=None if ok else "timeout", input_tokens=tin, output_tokens=tout)


def issue(code: str, level: str = "error", poi: str | None = None) -> dict[str, Any]:
    return {"level": level, "code": code, "message": f"测试：{code}", "poiId": poi}


def report(*issues: dict[str, Any]) -> ValidationReport:
    errors = any(i["level"] == "error" for i in issues)
    return ValidationReport.model_validate(
        {"status": "failed" if errors else ("warning" if issues else "passed"), "issues": list(issues)}
    )


def with_rounds(v: ItineraryVersionData, *, final_draft: PlanDraft, first: ValidationReport | None = None,
                first_draft: PlanDraft | None = None) -> ItineraryVersionData:
    rounds = 2 if first is not None else 1
    planner = v.planner.model_copy(update={"rounds": rounds})
    return v.model_copy(update={"draft": final_draft, "firstValidation": first, "firstDraft": first_draft, "planner": planner})


def one_day(*ids: str) -> ItineraryVersionData:
    times = [("09:00", "10:00"), ("10:30", "11:30"), ("12:00", "13:00"), ("13:30", "14:30")]
    stops = [stop(p, *times[i]) for i, p in enumerate(ids)]
    legs = [leg(a, b, 20) for a, b in zip(ids, ids[1:])]
    v = version((stops, legs), issues=[issue("data-pending", "warning")])
    return with_rounds(v, final_draft=draft([(p, *times[i]) for i, p in enumerate(ids)]))


# ---------- 调用记录 ----------


def test_call_stats_adds_up_records() -> None:
    s = call_stats([
        call("generate_itinerary", 9000, attempts=2, retried=True, tin=1000, tout=400),
        call("repair_itinerary", 6000, repaired=True, attempts=2, tin=None, tout=None),
    ])
    assert s.callCount == 2 and s.requestCount == 4
    assert s.retriedCalls == 1 and s.reaskedCalls == 1 and s.failedCalls == 0
    assert s.modelMs == 15000
    # 没返回 token 的不猜，单独数出来
    assert s.inputTokens == 1000 and s.outputTokens == 400 and s.tokensUnknownCalls == 1
    assert s.byTask == {"generate_itinerary": 1, "repair_itinerary": 1}


def test_call_stats_tokens_unknown_when_none_returned() -> None:
    s = call_stats([call("generate_itinerary", 100, tin=None, tout=None)])
    assert s.inputTokens is None and s.outputTokens is None and s.tokensUnknownCalls == 1


# ---------- 校验情况 ----------


def test_first_round_passes_with_warnings_only() -> None:
    q = quality_metrics(one_day("a", "b"), LIBRARY)
    # 有警告也算通过：通过指没有错误
    assert q.firstPassed and q.finalPassed and not q.repaired
    assert q.firstWarningCount == 1 and q.firstErrorCount == 0 and q.firstErrorCodes == {}


def test_repaired_counts_first_round_error_types() -> None:
    base = one_day("a", "b")
    first = report(issue("overlap"), issue("overlap"), issue("closed-day", poi="a"), issue("data-pending", "warning"))
    v = with_rounds(base, final_draft=base.draft, first=first, first_draft=base.draft)
    q = quality_metrics(v, LIBRARY)
    assert not q.firstPassed and q.firstErrorCount == 3 and q.firstWarningCount == 1
    assert q.firstErrorCodes == {"overlap": 2, "closed-day": 1}
    assert q.repaired and q.finalPassed and q.finalErrorCodes == {}


def test_still_failing_after_repair() -> None:
    base = one_day("a", "b")
    failed = base.model_copy(update={"validation": report(issue("transport-too-short"))})
    v = with_rounds(failed, final_draft=base.draft, first=report(issue("overlap")), first_draft=base.draft)
    q = quality_metrics(v, LIBRARY)
    assert q.repaired and not q.finalPassed and q.finalStatus == "failed"
    assert q.finalErrorCodes == {"transport-too-short": 1}


def test_fabricated_and_off_list_are_told_apart() -> None:
    base = one_day("a", "b")
    first_draft = draft([("a", "09:00", "10:00"), ("made-up", "10:30", "11:30"), ("avoided", "12:00", "13:00")])
    first = report(issue("unknown-poi", poi="made-up"), issue("unknown-poi", poi="avoided"))
    v = with_rounds(base, final_draft=base.draft, first=first, first_draft=first_draft)
    q = quality_metrics(v, LIBRARY)
    # made-up 在整个景点库里都没有，是编造；avoided 在库里，只是这次不能用
    assert q.firstFabricatedPoiIds == ["made-up"]
    assert q.firstOffListPoiIds == ["avoided"]
    assert q.finalFabricatedPoiIds == [] and q.finalOffListPoiIds == []


def test_repaired_version_without_first_report_is_an_error() -> None:
    base = one_day("a")
    v = base.model_copy(update={"planner": base.planner.model_copy(update={"rounds": 2})})
    with pytest.raises(ValueError):
        first_round(v)


# ---------- 差异 ----------


def test_diff_only_one_side_and_both() -> None:
    d = plan_diff(one_day("a", "b", "c"), one_day("b", "d"))
    assert [r.poiId for r in d.onlyLeft] == ["a", "c"]
    assert [r.poiId for r in d.onlyRight] == ["d"]
    assert [r.poiId for r in d.both] == ["b"]
    # 同一天都有的只有 1 个，谈不上顺序
    assert d.days[0].sameOrder is None


def test_diff_same_day_order() -> None:
    same = plan_diff(one_day("a", "b", "c"), one_day("a", "d", "c"))
    assert same.days[0].sameOrder is True and [r.poiId for r in same.days[0].common] == ["a", "c"]
    flipped = plan_diff(one_day("a", "b", "c"), one_day("c", "b", "a"))
    assert flipped.days[0].sameOrder is False


def test_diff_moved_to_other_day() -> None:
    t = [("09:00", "10:00"), ("10:30", "11:30")]

    def two_days(d1: list[str], d2: list[str]) -> ItineraryVersionData:
        days = []
        drafts = []
        for ids in (d1, d2):
            days.append(([stop(p, *t[i]) for i, p in enumerate(ids)], [leg(a, b, 20) for a, b in zip(ids, ids[1:])]))
            drafts.append([(p, *t[i]) for i, p in enumerate(ids)])
        return with_rounds(version(*days), final_draft=draft(*drafts))

    d = plan_diff(two_days(["a", "b"], ["c"]), two_days(["a"], ["b", "c"]))
    assert [(m.poiId, m.days) for m in d.moved] == [("b", [1, 2])]
    assert d.onlyLeft == [] and d.onlyRight == []


def test_diff_reuses_near_duplicate() -> None:
    assert plan_diff(one_day("a", "b"), one_day("a", "b")).nearDuplicate is not None
    assert plan_diff(one_day("a", "b"), one_day("c", "d")).nearDuplicate is None


# ---------- 对比表 ----------


def test_table_with_one_side_failed() -> None:
    v = one_day("a", "b")
    ok = side_result(provider="qwen", provider_label="通义千问", calls=[call("generate_itinerary", 8000)],
                     wall_ms=9000, library_ids=LIBRARY, version=v, version_id="v1")
    bad = side_result(provider="doubao", provider_label="豆包", calls=[call("generate_itinerary", 60000, ok=False, tin=None, tout=None)],
                      wall_ms=60100, library_ids=LIBRARY, error="排行程超时")
    t = comparison_table([ok, bad], [v, None], {"a": "测试景点a", "b": "测试景点b"})
    rows = {r.key: r for r in t.rows}
    assert t.labels == ["通义千问", "豆包"]
    assert rows["firstCheck"].texts == ["通过：0 条错误、1 条警告", "模型没排出来：排行程超时"]
    # 5B 的行程数字：排出来的一边有，没排出来的一边写 —
    assert rows["places"].texts == ["测试景点a、测试景点b", "—"]
    assert rows["validation"].label == "最终校验"
    # 耗时和调用两边都有
    assert rows["modelTime"].texts == ["8.0 秒", "60.0 秒"]
    assert rows["calls"].texts[1] == "1 次调用，发了 1 次请求（1 次失败）"
    assert rows["tokens"].texts == ["输入 100、输出 50", "不详"]


def test_table_both_sides_has_plan_rows_and_names_for_bad_pois() -> None:
    left = one_day("a", "b")
    first = report(issue("unknown-poi", poi="avoided"))
    right_base = one_day("c")
    right = with_rounds(right_base, final_draft=right_base.draft, first=first,
                        first_draft=draft([("c", "09:00", "10:00"), ("avoided", "10:30", "11:30")]))
    sides = [
        side_result(provider=p, provider_label=lab, calls=[call("generate_itinerary", 1000)], wall_ms=1000,
                    library_ids=LIBRARY, version=v)
        for p, lab, v in (("qwen", "通义千问", left), ("doubao", "豆包", right))
    ]
    t = comparison_table(sides, [left, right], {"avoided": "被排除的景点"})
    rows = {r.key: r for r in t.rows}
    assert {"stopCount", "transportMinutes", "walkingMeters", "tickets", "end-day-1"} <= rows.keys()
    assert rows["stopCount"].texts == ["2 个", "1 个"]
    assert rows["offList"].texts == ["没有", "1 个：被排除的景点"]
    assert rows["repair"].texts == ["没修正（第一版没有错误）", "修正一次后通过"]
    assert rows["firstCodes"].texts[1] == "不在候选里的景点 ×1"


# ---------- 汇总 ----------


def test_summary_rates_include_model_errors_in_denominator() -> None:
    passed = one_day("a", "b")
    base = one_day("a")
    repaired = with_rounds(base, final_draft=base.draft, first=report(issue("overlap"), issue("closed-day")), first_draft=base.draft)
    failing = with_rounds(base.model_copy(update={"validation": report(issue("overlap"))}), final_draft=base.draft,
                          first=report(issue("overlap"), issue("unknown-poi", poi="made-up")),
                          first_draft=draft([("a", "09:00", "10:00"), ("made-up", "10:30", "11:30")]))
    sides = [
        side_result(provider="qwen", provider_label="通义千问", calls=[call("generate_itinerary", 10000)], wall_ms=12000,
                    library_ids=LIBRARY, version=v)
        for v in (passed, repaired, failing)
    ]
    sides.append(side_result(provider="qwen", provider_label="通义千问", calls=[call("generate_itinerary", 60000, ok=False)],
                             wall_ms=60000, library_ids=LIBRARY, error="超时"))
    sides.append(side_result(provider="doubao", provider_label="豆包", calls=[call("generate_itinerary", 5000)], wall_ms=6000,
                             library_ids=LIBRARY, version=passed))

    s = summarize(sides, "qwen")
    assert s.runs == 4 and s.model_errors == 1
    assert s.first_passed == 1 and s.first_pass_rate == 0.25
    assert s.final_passed == 2 and s.final_pass_rate == 0.5
    # 平均第一版错误：0、2、2 → 4/3（出错的那次没有行程，不算）
    assert s.avg_first_errors == pytest.approx(4 / 3)
    assert s.top_error_codes == [("overlap", 2), ("closed-day", 1), ("unknown-poi", 1)]
    assert s.fabricated_runs == 1
    # 耗时按排出来的 3 次平均，不算等到超时的那次
    assert s.avg_model_seconds == pytest.approx(10.0) and s.avg_wall_seconds == pytest.approx(12.0)
    assert summarize(sides, "doubao").runs == 1
