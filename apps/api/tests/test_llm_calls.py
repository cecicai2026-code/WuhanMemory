"""大模型调用记录写进 SQLite 的测试。用临时数据库文件和假 provider，不联网。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.services.llm.errors import LLMAuthError, LLMUpstreamError
from app.services.llm.gateway import LLMGateway
from app.repositories.llm_call_repository import SqliteLLMCallRepository
from tests.llm_fakes import FakeProvider, Sleeps

GOOD = '{"city": "武汉"}'
SECRET_PROMPT = "这句提示词不应该被存进数据库"


def make(tmp_path: Path, *providers: FakeProvider) -> tuple[LLMGateway, SqliteLLMCallRepository]:
    calls = SqliteLLMCallRepository(tmp_path / "test.db")
    gateway = LLMGateway(
        providers={provider.name: provider for provider in providers},
        default_provider=providers[0].name,
        recorder=calls.add,
        sleep=Sleeps(),
    )
    return gateway, calls


async def ask(gateway: LLMGateway, **overrides):
    arguments = {"task": "test", "system_prompt": "你是测试助手。", "user_prompt": SECRET_PROMPT}
    arguments.update(overrides)
    return await gateway.complete_json(**arguments)


async def test_successful_call_is_stored(tmp_path: Path) -> None:
    gateway, calls = make(tmp_path, FakeProvider("a", script=[LLMUpstreamError("出错"), "不是 JSON", GOOD]))

    result = await ask(gateway, task="ping")

    assert calls.recent() == [result.record]
    stored = calls.recent()[0]
    assert (stored.task, stored.provider, stored.model) == ("ping", "a", "fake-model-1")
    assert (stored.attempts, stored.retried, stored.repaired, stored.ok) == (3, True, True, True)


async def test_failed_call_is_stored_with_error_code(tmp_path: Path) -> None:
    gateway, calls = make(tmp_path, FakeProvider("a", script=[LLMAuthError("key 无效")]))

    with pytest.raises(LLMAuthError):
        await ask(gateway)

    stored = calls.recent()[0]
    assert (stored.ok, stored.error_code, stored.attempts) == (False, "invalid_key", 1)


async def test_recent_is_newest_first_and_can_filter_by_provider(tmp_path: Path) -> None:
    gateway, calls = make(tmp_path, FakeProvider("a", script=[GOOD, GOOD]), FakeProvider("b", script=[GOOD]))

    await ask(gateway, task="first")
    await ask(gateway, task="second", provider="b")
    await ask(gateway, task="third")

    assert [record.task for record in calls.recent()] == ["third", "second", "first"]
    assert [record.task for record in calls.recent(provider="b")] == ["second"]
    assert [record.task for record in calls.recent(limit=1)] == ["third"]


async def test_prompts_and_answers_are_not_stored(tmp_path: Path) -> None:
    gateway, _ = make(tmp_path, FakeProvider("a", script=[GOOD]))

    await ask(gateway)

    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        rows = conn.execute("SELECT * FROM llm_calls").fetchall()
    finally:
        conn.close()
    stored_text = " ".join(str(value) for row in rows for value in row)
    assert SECRET_PROMPT not in stored_text
    assert "武汉" not in stored_text
