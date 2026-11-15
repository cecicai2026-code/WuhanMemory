"""豆包深度思考对比脚本的测试。脚本本身是给真实接口用的；这里用假模型、假高德，只测它怎么跑、打印什么。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from app.services.llm.base import LLMCallRecord
from app.services.llm.gateway import LLMGateway
from app.tools.thinking_compare import _prompts, main, run_all, summarize
from tests.llm_fakes import FakeProvider, Sleeps
from tests.test_planning_pipeline import DATED, Setup, plan, prefs


def maker(tmp_path: Path, scripts: dict[str, list[list[Any]]]):
    """scripts[mode] 是这个模式下每次运行的剧本，按顺序用。"""
    used: list[str] = []

    @asynccontextmanager
    async def make(mode: str) -> AsyncIterator[tuple[Any, list[LLMCallRecord]]]:
        used.append(mode)
        records: list[LLMCallRecord] = []
        s = Setup(tmp_path / f"{mode}{len(used)}", [], routes={("a", "b", "walk"): 10})
        model = FakeProvider("doubao", script=scripts[mode].pop(0), model=f"doubao-{mode}")
        s.pipeline.gateway = LLMGateway(providers={"doubao": model}, default_provider="doubao", sleep=Sleeps(), recorder=records.append)
        yield s.pipeline, records

    return make, used


async def test_runs_each_prompt_in_both_modes_and_alternates(tmp_path: Path) -> None:
    good = [prefs(**DATED), plan([("a", "09:30", "11:30"), ("b", "12:00", "14:00")])]
    bad_then_good = [prefs(**DATED), plan([("a", "09:30", "11:30"), ("b", "11:35", "14:00")]), plan([("a", "09:30", "11:30"), ("b", "12:00", "14:00")])]
    make, used = maker(tmp_path, {"enabled": [good, good], "disabled": [bad_then_good, good]})
    lines: list[str] = []

    results = await run_all(make, ["请求"], repeat=2, out=lines.append)

    assert used == ["enabled", "disabled", "disabled", "enabled"]
    assert [r.status for r in results] == ["passed", "passed", "passed", "passed"]
    assert results[1].rounds == 2 and results[1].first_errors == 1
    assert results[0].model == "doubao-enabled"
    assert [c.task for c in results[1].calls] == ["extract_preferences", "generate_itinerary", "repair_itinerary"]
    assert "修正过" in lines[1] and "开着思考" in lines[0]

    summary: list[str] = []
    summarize(results, summary.append)
    text = "\n".join(summary)
    assert "开着思考：跑了 2 次" in text and "关着思考：跑了 2 次" in text
    assert "需要修正的 1 次" in text
    assert "doubao-disabled" in text


async def test_errors_and_questions_are_counted(tmp_path: Path) -> None:
    from app.services.llm.errors import LLMTimeoutError

    make, _ = maker(tmp_path, {"enabled": [[LLMTimeoutError("测试：超时")] * 3], "disabled": [[prefs()]]})
    lines: list[str] = []
    results = await run_all(make, ["请求"], repeat=1, out=lines.append)
    assert results[0].error and results[0].error.startswith("timeout")
    assert results[1].kind == "question"
    summary: list[str] = []
    summarize(results, summary.append)
    assert "出错 1 次" in "\n".join(summary) and "被反问 1 次" in "\n".join(summary)


def test_prompts_have_a_future_date() -> None:
    ps = _prompts("2026-11-15")
    assert len(ps) == 3 and all("2026-11-22" in p for p in ps)


def test_stray_double_dash_is_ignored(capsys) -> None:
    """pnpm 有时把 "--" 原样传进来；--help 能正常打印就说明参数解析过了这一关。"""
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["--", "--timeout", "180", "--help"])
    assert exc.value.code == 0
    assert "--timeout" in capsys.readouterr().out
