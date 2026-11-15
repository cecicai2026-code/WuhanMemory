"""批量评测脚本的测试（板块 6）。用两个假模型和假高德，不调用真实接口；景点、行程、耗时都是测试值。"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from pathlib import Path

import pytest

from app.repositories.model_comparison_repository import SqliteModelComparisonRepository
from app.services.llm.errors import LLMAuthError
from app.services.planning.compare_runner import ModelComparer
from app.tools.model_eval import (
    CSV_COLUMNS,
    REQUESTS_PATH,
    DataFacts,
    EvalRequest,
    call_plan,
    load_requests,
    main,
    output_paths,
    render_csv,
    render_summary,
    run_eval,
)
from tests.test_plan_single import GOOD, TwoModels
from tests.test_planning_pipeline import plan

CLASH = plan([("a", "09:30", "11:30"), ("b", "11:35", "14:00")])  # 空档 5 分钟，走路要 12 分钟
FACTS = DataFacts(pois=3, open_pois=3, facts=30, onsite=0, confirmed=20, placeholder=6, todo=4, expired=0)


def req(rid: str, emphasis: str = "classic") -> EvalRequest:
    return EvalRequest.model_validate(
        {"id": rid, "text": f"测试请求 {rid}", "preferences": {"days": 1, "startDate": "2026-11-17"}, "emphasis": emphasis}
    )


def test_requests_file_is_valid() -> None:
    # 仓库里的 eval/requests.json 能读，id 不重复，侧重和天数都有
    items = load_requests(REQUESTS_PATH)
    assert len(items) >= 1 and all(r.preferences.days for r in items)


@pytest.mark.parametrize(
    "bad, words",
    [
        ([{"id": "x", "text": "t", "preferences": {"days": 1}, "emphasis": "nope"}], "侧重"),
        ([{"id": "x", "text": "t", "preferences": {}, "emphasis": "classic"}], "天数"),
        ([{"id": "x", "text": "t", "preferences": {"days": 1}, "emphasis": "classic"}] * 2, "重复"),
        ([{"id": "x", "preferences": {"days": 1}, "emphasis": "classic"}], "格式"),
    ],
)
def test_bad_requests_file(tmp_path: Path, bad: list, words: str) -> None:
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"requests": bad}), encoding="utf-8")
    with pytest.raises(ValueError, match=words):
        load_requests(p)


def test_call_plan() -> None:
    p = call_plan(10, 1)
    assert (p.comparisons, p.min_calls, p.max_calls) == (10, 20, 40)
    assert call_plan(10, 3).max_calls == 120


async def test_run_writes_csv_and_summary(tmp_path: Path) -> None:
    # r01：千问一次通过，豆包第一版有错、修正后通过；r02：千问通过，豆包模型出错
    s = TwoModels(tmp_path, [GOOD, GOOD], [CLASH, GOOD, LLMAuthError("测试：额度")])
    repo = SqliteModelComparisonRepository(tmp_path / "t.db")
    lines: list[str] = []
    runs = await run_eval(ModelComparer(s.pipeline, repo), [req("r01"), req("r02")], 1, out=lines.append)
    assert len(runs) == 2 and len(lines) == 2
    assert all(r.comparison.evalRequestId for r in runs) and len(repo.list()) == 2

    rows = list(csv.DictReader(io.StringIO(render_csv(runs))))
    assert len(rows) == 4 and list(rows[0].keys()) == CSV_COLUMNS
    doubao_r01 = next(r for r in rows if r["request_id"] == "r01" and r["provider"] == "doubao")
    assert doubao_r01["first_passed"] == "0" and doubao_r01["repaired"] == "1" and doubao_r01["final_passed"] == "1"
    assert "transport-too-short" in doubao_r01["first_error_codes"]
    doubao_r02 = next(r for r in rows if r["request_id"] == "r02" and r["provider"] == "doubao")
    assert "额度" in doubao_r02["error"] and doubao_r02["first_passed"] == ""

    md = render_summary(runs, run_date=date(2026, 11, 15), repeat=1, facts=FACTS, csv_name="2026-11-15.csv")
    # 千问 2/2 首次通过；豆包 0/2 首次通过、1/2 修正后通过（模型出错的也在分母里）
    assert "| 首次通过率（第一版没有错误） | 100%（2/2） | 0%（0/2） |" in md
    assert "| 修正后通过率 | 100%（2/2） | 50%（1/2） |" in md
    assert "| 模型出错（没排出来） | 0 | 1 |" in md
    assert "交通时间不够（transport-too-short）1 次" in md
    assert "请求只有 2 条" in md and "景点库只有 3 个景点" in md and "占位 6" in md
    assert "不下\"哪个模型更好\"的结论" in md


def test_output_paths_do_not_overwrite(tmp_path: Path) -> None:
    c1, m1 = output_paths(tmp_path, date(2026, 11, 15))
    assert c1.name == "2026-11-15.csv" and m1.name == "2026-11-15.md"
    c1.write_text("x")
    c2, m2 = output_paths(tmp_path, date(2026, 11, 15))
    assert c2.name == "2026-11-15-2.csv" and m2.name == "2026-11-15-2.md"


def test_dry_run_does_not_call_models(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"requests": [req("r01").model_dump(mode="json"), req("r02").model_dump(mode="json")]}),
                 encoding="utf-8")
    assert main(["--", "--dry-run", "--requests", str(p), "--repeat", "2"]) == 0
    out = capsys.readouterr().out
    assert "4 次对比" in out and "8 到 16 次" in out and "没有调用模型" in out


async def test_failed_side_never_shows_configured_model_and_rerender(tmp_path: Path) -> None:
    """模型出错那一边：失败的调用里记的是配置的模型设置（豆包是推理接入点 ID），不能当模型名写出去。"""
    from tests.test_plan_single import TwoModels as _TwoModels

    s = _TwoModels(tmp_path, [GOOD], [LLMAuthError("测试：额度")])
    s.doubao.model = "ep-test-endpoint"  # 假的接入点 ID
    repo = SqliteModelComparisonRepository(tmp_path / "t.db")
    runs = await run_eval(ModelComparer(s.pipeline, repo), [req("r01")], 1, out=lambda _: None)
    side = runs[0].comparison.sides[1]
    assert side.quality is None and side.model is None
    text = render_csv(runs) + render_summary(runs, run_date=date(2026, 11, 15), repeat=1, facts=FACTS, csv_name="x.csv")
    assert "ep-test-endpoint" not in text

    # 以前存成了接入点 ID 的旧数据：读出来时清空
    import sqlite3

    conn = sqlite3.connect(tmp_path / "t.db")
    raw = conn.execute("SELECT data_json FROM model_comparisons").fetchone()[0]
    data = json.loads(raw)
    data["sides"][1]["model"] = "ep-test-endpoint"
    with conn:
        conn.execute("UPDATE model_comparisons SET data_json = ?", (json.dumps(data),))
    conn.close()
    assert repo.get(runs[0].comparison.id).sides[1].model is None  # type: ignore[union-attr]

    # 重新生成：按 CSV 里的对比 id 从数据库取，不调用模型，数字不变
    csv_path = tmp_path / "2026-11-15.csv"
    csv_path.write_text(render_csv(runs), encoding="utf-8")
    from app.tools.model_eval import rerender

    new_csv, new_md = rerender(csv_path, [req("r01")], repo, FACTS)
    assert "ep-test-endpoint" not in new_csv + new_md
    assert new_csv == render_csv(runs)
    assert "| 模型出错（没排出来） | 0 | 1 |" in new_md
