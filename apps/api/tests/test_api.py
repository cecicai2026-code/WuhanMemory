"""对话和规划接口的测试。规划链路换成用假模型、假高德、临时 SQLite 建的，不联网。

TestClient 会在返回回应之前把后台任务跑完，所以发完消息马上查任务，就能看到结果。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.planning import get_conversations, get_itineraries, get_job_store, get_pipeline_factory, get_rounds
from app.main import app
from app.repositories.conversation_repository import SqliteConversationRepository
from app.repositories.itinerary_repository import SqliteItineraryRepository
from app.repositories.planning_round_repository import SqlitePlanningRoundRepository
from app.services.llm.errors import LLMAuthError, LLMRateLimitError
from app.services.planning.jobs import JobStore
from tests.test_planning_pipeline import DATED, Setup, plan, prefs


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Any]:
    def install(script: list[Any], routes: dict | None = None, provider_name: str = "fake", **setup: Any) -> tuple[TestClient, Setup]:
        s = Setup(tmp_path, script, routes, **setup)
        s.model.name = provider_name
        s.pipeline.gateway._providers = {provider_name: s.model}  # noqa: SLF001
        s.pipeline.gateway.default_provider = provider_name

        @asynccontextmanager
        async def factory() -> AsyncIterator[Any]:
            yield s.pipeline

        db = tmp_path / "t.db"
        app.dependency_overrides[get_pipeline_factory] = lambda: factory
        app.dependency_overrides[get_conversations] = lambda: SqliteConversationRepository(db)
        app.dependency_overrides[get_itineraries] = lambda: SqliteItineraryRepository(db)
        app.dependency_overrides[get_rounds] = lambda: SqlitePlanningRoundRepository(db)
        store = JobStore()
        app.dependency_overrides[get_job_store] = lambda: store
        return TestClient(app), s

    yield install
    app.dependency_overrides.clear()


def start(client: TestClient) -> str:
    response = client.post("/api/conversations", json={"city": "武汉"})
    assert response.status_code == 200
    return response.json()["conversationId"]


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200 and response.json()["status"] == "ok"


def test_message_to_itinerary(api) -> None:
    client, s = api([prefs(**DATED), plan([("a", "09:30", "11:30")])])
    conv = start(client)
    sent = client.post(f"/api/conversations/{conv}/messages", json={"content": "下周二去一天", "provider": "fake"})
    assert sent.status_code == 202
    job = client.get(f"/api/planning-jobs/{sent.json()['planningJobId']}").json()
    assert job["status"] == "completed" and job["kind"] == "itinerary" and job["provider"] == "fake"
    assert [st["id"] for st in job["stages"]] == ["understanding", "selecting", "generating", "routing", "validating", "saving"]
    assert job["stages"][0]["label"] == "理解需求"

    version = client.get(f"/api/itinerary-versions/{job['itineraryVersionId']}").json()
    assert version["versionNumber"] == 1 and version["planner"]["provider"] == "fake"
    assert version["validation"]["status"] == "passed"
    assert version["days"][0]["stops"][0]["facts"]["openingHours"]["status"] == "verified"

    convo = client.get(f"/api/conversations/{conv}").json()
    assert [m["role"] for m in convo["messages"]] == ["user", "assistant"]
    assert convo["messages"][1]["itineraryVersionId"] == version["id"]
    assert convo["preferences"]["days"] == 1


def test_question_job(api) -> None:
    client, _ = api([prefs()])
    conv = start(client)
    job_id = client.post(f"/api/conversations/{conv}/messages", json={"content": "去武汉"}).json()["planningJobId"]
    job = client.get(f"/api/planning-jobs/{job_id}").json()
    assert job["kind"] == "question" and "几天" in job["reply"] and job["itineraryVersionId"] is None


def test_failed_validation_is_a_completed_job_with_failed_kind(api) -> None:
    bad = plan([("a", "10:00", "12:00")])
    client, _ = api([prefs(days=1, startDate="2026-11-16"), bad, bad])
    conv = start(client)
    job_id = client.post(f"/api/conversations/{conv}/messages", json={"content": "周一"}).json()["planningJobId"]
    job = client.get(f"/api/planning-jobs/{job_id}").json()
    assert job["status"] == "completed" and job["kind"] == "failed"
    version = client.get(f"/api/itinerary-versions/{job['itineraryVersionId']}").json()
    assert version["validation"]["status"] == "failed"


@pytest.mark.parametrize(
    ("script", "code", "retryable"),
    [([LLMAuthError("key 无效")], "invalid_key", False), ([LLMRateLimitError("限流")] * 3, "rate_limited", True)],
)
def test_model_error_is_reported_on_the_job(api, script, code, retryable) -> None:
    client, _ = api(script)
    conv = start(client)
    job_id = client.post(f"/api/conversations/{conv}/messages", json={"content": "去"}).json()["planningJobId"]
    job = client.get(f"/api/planning-jobs/{job_id}").json()
    assert job["status"] == "failed"
    assert (job["error"]["code"], job["error"]["retryable"]) == (code, retryable)
    messages = client.get(f"/api/conversations/{conv}").json()["messages"]
    assert messages[-1]["kind"] == "error"


def test_unknown_provider_is_reported(api) -> None:
    client, _ = api([])
    conv = start(client)
    job_id = client.post(f"/api/conversations/{conv}/messages", json={"content": "去", "provider": "gpt"}).json()["planningJobId"]
    assert client.get(f"/api/planning-jobs/{job_id}").json()["error"]["code"] == "unknown_provider"


def test_bad_requests(api) -> None:
    client, _ = api([])
    assert client.post("/api/conversations/conv_nope/messages", json={"content": "去"}).status_code == 404
    conv = start(client)
    assert client.post(f"/api/conversations/{conv}/messages", json={"content": "  "}).status_code == 400
    assert client.get("/api/planning-jobs/job_nope").status_code == 404
    assert client.get("/api/itinerary-versions/ver_nope").status_code == 404
    assert client.get("/api/conversations/conv_nope").status_code == 404


def test_one_job_per_conversation(api) -> None:
    client, _ = api([])
    conv = start(client)
    assert client.get(f"/api/conversations/{conv}").json()["runningJobId"] is None
    store = app.dependency_overrides[get_job_store]()
    job = store.create(conv, None)  # 假装上一条还在跑
    assert client.post(f"/api/conversations/{conv}/messages", json={"content": "去"}).status_code == 409
    # 刷新页面后，前端从这里拿到还在跑的任务，接着显示进度
    assert client.get(f"/api/conversations/{conv}").json()["runningJobId"] == job.id


def test_share_not_implemented_yet() -> None:
    client = TestClient(app)
    assert client.get("/api/share/anything").status_code == 404



def test_planning_round_with_comparison(api) -> None:
    from tests.test_planning_rounds import ALL, CLASSIC, CULTURE, POIS, WALKS

    # 和经典的几乎一样。钟点由程序推：轻松那份走 12 分钟超过 10 分钟，坐地铁 20 分钟，b 12:00–14:10（经典的 b 11:55–13:55）
    dup = plan([("a", "09:30", "11:30"), ("b", "12:00", "14:10")])
    client, s = api([prefs(**DATED), CLASSIC, dup, CULTURE], routes={**WALKS, ("a", "b", "transit"): 20}, pois=POIS, emphases=ALL)
    conv = start(client)
    job_id = client.post(f"/api/conversations/{conv}/messages", json={"content": "下周二去一天"}).json()["planningJobId"]
    job = client.get(f"/api/planning-jobs/{job_id}").json()
    round_id = job["planningRoundId"]
    assert round_id

    rnd = client.get(f"/api/planning-rounds/{round_id}").json()
    assert [p["label"] for p in rnd["plans"]] == ["经典必去", "轻松少走路", "深度文化"]
    assert [p["shown"] for p in rnd["plans"]] == [True, False, True]
    assert rnd["plans"][1]["removedReason"].startswith("和「经典必去」几乎一样")
    # 只给展示的两份版本和比较表
    assert [v["emphasis"] for v in rnd["versions"]] == ["classic", "culture"]
    assert rnd["comparison"]["labels"] == ["经典必去", "深度文化"]
    rows = {r["key"]: r for r in rnd["comparison"]["rows"]}
    assert rows["places"]["texts"] == ["测试景点a、测试景点b", "测试景点a、测试景点b"]
    # 经典：b 11:55 到、待 120 分钟；深度文化：a 09:00–11:00，走 12 分钟 + 10 → 11:25 到 b、待 210 分钟
    assert rows["end-day-1"]["texts"] == ["13:55", "14:55"]

    convo = client.get(f"/api/conversations/{conv}").json()
    assert convo["messages"][-1]["planningRoundId"] == round_id
    assert client.get("/api/planning-rounds/round_nope").status_code == 404
