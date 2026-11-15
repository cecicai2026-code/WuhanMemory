"""双模型对比的整条流程和接口测试（板块 6）。两个假模型（名字叫 qwen、doubao）、假高德、临时 SQLite，不联网。

景点是虚构的测试景点；行程、耗时、token 都是测试值。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.comparisons import CompareJobStore, get_compare_jobs, get_comparisons, get_gateway
from app.api.planning import get_itineraries, get_pipeline_factory
from app.main import app
from app.repositories.model_comparison_repository import SqliteModelComparisonRepository
from app.schemas.planning import TravelerPreferences
from app.services.llm.errors import LLMAuthError
from app.services.planning.compare_runner import ModelComparer, NeedsMoreInfo
from tests.test_plan_single import GOOD, PREFS, TwoModels
from tests.test_planning_pipeline import plan, prefs

OTHER = plan([("a", "09:30", "11:30"), ("c", "13:30", "15:30")])  # a 到 c 假高德公交 99 分钟，留够空档


def comparer(s: TwoModels, tmp_path: Path) -> tuple[ModelComparer, SqliteModelComparisonRepository]:
    repo = SqliteModelComparisonRepository(tmp_path / "t.db")
    return ModelComparer(s.pipeline, repo), repo


async def test_extracts_once_then_both_models_plan(tmp_path: Path) -> None:
    s = TwoModels(tmp_path, [prefs(days=1, startDate="2026-11-17"), GOOD], [OTHER])
    c, repo = comparer(s, tmp_path)
    progress: list[tuple[str | None, str]] = []
    out = await c.compare("下周二去一天", on_progress=lambda p, st: progress.append((p, st)))

    # 偏好只抽了一次（默认模型 qwen），两边共用
    assert out.preferencesSource == "extracted" and out.extractor == "qwen"
    assert out.extractorCalls is not None and out.extractorCalls.byTask == {"extract_preferences": 1}
    assert len(s.qwen.calls) == 2 and len(s.doubao.calls) == 1
    # 两边排行程的提示词一样
    assert s.qwen.calls[1] == s.doubao.calls[0]
    # 每边的调用只算自己的排行程，不含抽偏好
    assert [x.provider for x in out.sides] == ["qwen", "doubao"]
    assert all(x.calls.byTask == {"generate_itinerary": 1} for x in out.sides)
    assert out.sides[0].plan is not None and out.sides[0].plan.poiIds == ["a", "b"]
    # 差异：b 只在左边，c 只在右边
    assert out.diff is not None
    assert [r.poiId for r in out.diff.onlyLeft] == ["b"] and [r.poiId for r in out.diff.onlyRight] == ["c"]
    assert out.table.labels == ["假模型 qwen", "假模型 doubao"]
    # 存进了 SQLite，可以回看
    assert repo.get(out.id) is not None and repo.list()[0].id == out.id
    assert (None, "understanding") in progress and ("qwen", "done") in progress and ("doubao", "done") in progress


async def test_given_preferences_skip_extraction(tmp_path: Path) -> None:
    s = TwoModels(tmp_path, [GOOD], [GOOD])
    c, _ = comparer(s, tmp_path)
    out = await c.compare("测试请求", prefs=PREFS, emphasis="classic", eval_request_id="r01")
    assert out.preferencesSource == "given" and out.extractor is None and out.extractorCalls is None
    assert len(s.qwen.calls) == 1 and len(s.doubao.calls) == 1
    assert out.evalRequestId == "r01"
    # 两份一样：差异里写出几乎一样
    assert out.diff is not None and out.diff.nearDuplicate is not None


async def test_one_side_model_error(tmp_path: Path) -> None:
    s = TwoModels(tmp_path, [GOOD], [LLMAuthError("测试：额度")])
    c, repo = comparer(s, tmp_path)
    out = await c.compare("测试请求", prefs=PREFS)
    assert out.sides[0].quality is not None
    assert out.sides[1].quality is None and out.sides[1].error is not None and "额度" in out.sides[1].error
    assert out.sides[1].calls.failedCalls == 1
    assert out.diff is None
    brief = repo.list()[0].sides
    assert brief[1].error and brief[1].firstPassed is None and brief[0].firstPassed is True


async def test_needs_days(tmp_path: Path) -> None:
    s = TwoModels(tmp_path, [prefs()], [])
    c, repo = comparer(s, tmp_path)
    with pytest.raises(NeedsMoreInfo):
        await c.compare("想去武汉")
    assert repo.list() == []


async def test_bad_emphasis(tmp_path: Path) -> None:
    c, _ = comparer(TwoModels(tmp_path, [], []), tmp_path)
    with pytest.raises(ValueError):
        await c.compare("去", prefs=PREFS, emphasis="nope")


# ---------- 接口 ----------


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Any]:
    def install(qwen: list[Any], doubao: list[Any]) -> tuple[TestClient, TwoModels, CompareJobStore]:
        s = TwoModels(tmp_path, qwen, doubao)

        @asynccontextmanager
        async def factory() -> AsyncIterator[Any]:
            yield s.pipeline

        from app.repositories.itinerary_repository import SqliteItineraryRepository

        db = tmp_path / "t.db"
        store = CompareJobStore()
        app.dependency_overrides[get_pipeline_factory] = lambda: factory
        app.dependency_overrides[get_itineraries] = lambda: SqliteItineraryRepository(db)
        app.dependency_overrides[get_comparisons] = lambda: SqliteModelComparisonRepository(db)
        app.dependency_overrides[get_compare_jobs] = lambda: store
        app.dependency_overrides[get_gateway] = lambda: s.gateway
        return TestClient(app), s, store

    yield install
    app.dependency_overrides.clear()


def test_api_runs_and_reads_back(api) -> None:
    client, _, _ = api([prefs(days=1, startDate="2026-11-17"), GOOD], [OTHER])
    r = client.post("/api/comparisons", json={"request": "下周二去一天"})
    assert r.status_code == 202
    job = client.get(f"/api/comparison-jobs/{r.json()['jobId']}").json()
    assert job["status"] == "completed", job
    assert job["stages"][0]["id"] == "understanding"
    assert [x["provider"] for x in job["sides"]] == ["qwen", "doubao"]
    assert job["sides"][0]["stages"][-1]["id"] == "done"

    cmp = client.get(f"/api/comparisons/{job['comparisonId']}").json()
    assert len(cmp["versions"]) == 2 and cmp["versions"][1]["planner"]["provider"] == "doubao"
    assert cmp["table"]["rows"][0]["key"] == "firstCheck"
    listed = client.get("/api/comparisons").json()
    assert listed[0]["id"] == cmp["id"] and listed[0]["sides"][0]["firstPassed"] is True


def test_api_needs_days_is_reported(api) -> None:
    client, _, _ = api([prefs()], [])
    job_id = client.post("/api/comparisons", json={"request": "想去武汉"}).json()["jobId"]
    job = client.get(f"/api/comparison-jobs/{job_id}").json()
    assert job["status"] == "failed" and job["error"]["code"] == "needs_days"


def test_api_bad_requests(api) -> None:
    client, s, store = api([], [])
    assert client.post("/api/comparisons", json={"request": "去", "emphasis": "nope"}).status_code == 400
    assert client.get("/api/comparisons/cmp_nope").status_code == 404
    assert client.get("/api/comparison-jobs/cjob_nope").status_code == 404
    store.create("上一条", "classic")  # 假装还有一次在跑
    assert client.post("/api/comparisons", json={"request": "去"}).status_code == 409


def test_api_needs_both_models_configured(api) -> None:
    client, s, _ = api([], [])
    s.doubao._configured = False  # noqa: SLF001
    r = client.post("/api/comparisons", json={"request": "去"})
    assert r.status_code == 400 and "doubao" in r.json()["detail"]


def test_given_preferences_type() -> None:
    # 手写的偏好和抽出来的用同一个结构
    assert TravelerPreferences.model_validate({"days": 2, "interests": ["美食"]}).days == 2
