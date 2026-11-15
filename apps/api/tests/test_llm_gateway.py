"""LLMGateway 的测试。不调用真实接口：用 tests/llm_fakes.py 里的假 provider，
测的是网关自己的行为：切换、重试、限流等待、超时、输出修复和调用记录。"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.services.llm.base import ProviderReply
from app.services.llm.errors import (
    LLMAuthError,
    LLMNotConfiguredError,
    LLMOutputFormatError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnknownProviderError,
    LLMUpstreamError,
)
from app.services.llm.gateway import JSON_ONLY_INSTRUCTION, LLMGateway
from tests.llm_fakes import FakeProvider, Records, Sleeps, Slow

GOOD = '{"city": "武汉", "days": 2}'


class Trip(BaseModel):
    city: str
    days: int


def make_gateway(*providers: FakeProvider, default: str | None = None, **options):
    sleeps, records = Sleeps(), Records()
    gateway = LLMGateway(
        providers={provider.name: provider for provider in providers},
        default_provider=default or providers[0].name,
        sleep=sleeps,
        recorder=records,
        **options,
    )
    return gateway, sleeps, records


async def ask(gateway: LLMGateway, **overrides):
    arguments = {"task": "test", "system_prompt": "你是测试助手。", "user_prompt": "去武汉玩两天"}
    arguments.update(overrides)
    return await gateway.complete_json(**arguments)


# ---- 正常调用和记录 ----


async def test_success_returns_payload_and_record() -> None:
    provider = FakeProvider("a", script=[GOOD])
    gateway, sleeps, records = make_gateway(provider)

    result = await ask(gateway, task="extract_preferences")

    assert result.payload == {"city": "武汉", "days": 2}
    assert result.provider == "a"
    assert result.model == "fake-model-1"
    assert sleeps.waits == []
    assert records.items == [result.record]
    record = result.record
    assert (record.task, record.provider, record.model) == ("extract_preferences", "a", "fake-model-1")
    assert (record.attempts, record.retried, record.repaired) == (1, False, False)
    assert record.ok and record.error_code is None
    assert record.latency_ms >= 0
    assert (record.input_tokens, record.output_tokens) == (10, 5)


async def test_system_prompt_gets_json_only_instruction() -> None:
    provider = FakeProvider("a", script=[GOOD])
    gateway, _, _ = make_gateway(provider)

    await ask(gateway)

    system, user = provider.calls[0]
    assert system.role == "system" and system.content.startswith("你是测试助手。")
    assert system.content.endswith(JSON_ONLY_INSTRUCTION)
    assert (user.role, user.content) == ("user", "去武汉玩两天")


async def test_record_uses_model_name_from_reply() -> None:
    """豆包请求里填的是 endpoint ID，记录里要的是对方返回的真实模型名。"""
    provider = FakeProvider("a", model="ep-test", script=[ProviderReply(text=GOOD, model="real-model-name")])
    gateway, _, _ = make_gateway(provider)

    result = await ask(gateway)

    assert result.model == "real-model-name"
    assert result.record.model == "real-model-name"


# ---- 切换 ----


async def test_default_provider_is_used_when_request_does_not_choose() -> None:
    a, b = FakeProvider("a", script=[GOOD]), FakeProvider("b", script=[GOOD])
    gateway, _, _ = make_gateway(a, b, default="b")

    result = await ask(gateway)

    assert result.provider == "b"
    assert len(b.calls) == 1 and a.calls == []


async def test_request_can_choose_provider() -> None:
    a, b = FakeProvider("a", script=[GOOD]), FakeProvider("b", script=[GOOD])
    gateway, _, records = make_gateway(a, b, default="a")

    result = await ask(gateway, provider="b")

    assert result.provider == "b"
    assert len(b.calls) == 1 and a.calls == []
    assert records.items[0].provider == "b"


async def test_unknown_provider_is_a_clear_error() -> None:
    gateway, _, _ = make_gateway(FakeProvider("a"))

    with pytest.raises(LLMUnknownProviderError) as error:
        await ask(gateway, provider="gpt")
    assert "gpt" in str(error.value) and "a" in str(error.value)


async def test_unknown_default_provider_is_a_clear_error() -> None:
    gateway, _, _ = make_gateway(FakeProvider("a"), default="mock")

    with pytest.raises(LLMUnknownProviderError) as error:
        await ask(gateway)
    assert "LLM_PROVIDER" in str(error.value)


async def test_unconfigured_provider_is_not_called() -> None:
    provider = FakeProvider("a", configured=False)
    gateway, _, records = make_gateway(provider)

    with pytest.raises(LLMNotConfiguredError):
        await ask(gateway)

    assert provider.calls == []
    assert (records.items[0].ok, records.items[0].error_code, records.items[0].attempts) == (False, "not_configured", 0)


def test_providers_lists_configured_and_default() -> None:
    gateway, _, _ = make_gateway(FakeProvider("a"), FakeProvider("b", configured=False), default="a")

    listed = {info.id: info for info in gateway.providers()}

    assert listed["a"].configured and listed["a"].is_default
    assert not listed["b"].configured and not listed["b"].is_default


# ---- 重试和等待 ----


async def test_retries_after_upstream_error() -> None:
    provider = FakeProvider("a", script=[LLMUpstreamError("服务器出错"), GOOD])
    gateway, sleeps, _ = make_gateway(provider)

    result = await ask(gateway)

    assert result.payload["city"] == "武汉"
    assert (result.record.attempts, result.record.retried, result.record.repaired) == (2, True, False)
    assert sleeps.waits == [1.0]


async def test_gives_up_after_max_retries_with_growing_waits() -> None:
    provider = FakeProvider("a", script=[LLMUpstreamError("1"), LLMUpstreamError("2"), LLMUpstreamError("3")])
    gateway, sleeps, records = make_gateway(provider, max_retries=2)

    with pytest.raises(LLMUpstreamError):
        await ask(gateway)

    assert len(provider.calls) == 3
    assert sleeps.waits == [1.0, 2.0]
    record = records.items[0]
    assert (record.ok, record.error_code, record.attempts, record.retried) == (False, "upstream_error", 3, True)


async def test_invalid_key_is_not_retried() -> None:
    provider = FakeProvider("a", script=[LLMAuthError("key 无效")])
    gateway, sleeps, records = make_gateway(provider)

    with pytest.raises(LLMAuthError):
        await ask(gateway)

    assert len(provider.calls) == 1 and sleeps.waits == []
    assert (records.items[0].error_code, records.items[0].retried) == ("invalid_key", False)


async def test_rate_limit_waits_as_long_as_provider_asks() -> None:
    provider = FakeProvider("a", script=[LLMRateLimitError("限流", retry_after=5), GOOD])
    gateway, sleeps, _ = make_gateway(provider)

    result = await ask(gateway)

    assert sleeps.waits == [5]
    assert result.record.retried


async def test_rate_limit_wait_is_capped() -> None:
    provider = FakeProvider("a", script=[LLMRateLimitError("限流", retry_after=120), GOOD])
    gateway, sleeps, _ = make_gateway(provider, max_rate_limit_wait_seconds=20)

    await ask(gateway)

    assert sleeps.waits == [20]


async def test_rate_limit_without_retry_after_backs_off() -> None:
    provider = FakeProvider("a", script=[LLMRateLimitError("限流"), LLMRateLimitError("限流"), GOOD])
    gateway, sleeps, _ = make_gateway(provider)

    await ask(gateway)

    assert sleeps.waits == [1.0, 2.0]


async def test_unexpected_provider_exception_becomes_provider_error() -> None:
    provider = FakeProvider("a", script=[RuntimeError("里面有不该出现在报错里的内容")])
    gateway, sleeps, records = make_gateway(provider)

    with pytest.raises(LLMProviderError) as error:
        await ask(gateway)

    assert "RuntimeError" in str(error.value)
    assert "不该出现" not in str(error.value)
    assert sleeps.waits == [] and records.items[0].error_code == "provider_error"


# ---- 超时（这里真的等，所以时间设得很短） ----


async def test_slow_provider_times_out() -> None:
    provider = FakeProvider("a", script=[Slow(1.0)])
    gateway, _, records = make_gateway(provider, timeout_seconds=0.05, max_retries=0)

    with pytest.raises(LLMTimeoutError):
        await ask(gateway)

    assert (records.items[0].error_code, records.items[0].attempts) == ("timeout", 1)


async def test_timeout_is_retried() -> None:
    provider = FakeProvider("a", script=[Slow(1.0), GOOD])
    gateway, sleeps, _ = make_gateway(provider, timeout_seconds=0.05)

    result = await ask(gateway)

    assert (result.record.attempts, result.record.retried) == (2, True)
    assert sleeps.waits == [1.0]


async def test_timeout_not_retried_when_asked() -> None:
    """排行程这种慢请求：超时直接报错，不让用户白等几轮。"""
    provider = FakeProvider("a", script=[Slow(1.0), GOOD])
    gateway, sleeps, records = make_gateway(provider, timeout_seconds=0.05)

    with pytest.raises(LLMTimeoutError):
        await ask(gateway, retry_on_timeout=False)

    assert (records.items[0].attempts, records.items[0].retried) == (1, False)
    assert sleeps.waits == []


async def test_rate_limit_still_retried_when_timeouts_are_not() -> None:
    provider = FakeProvider("a", script=[LLMRateLimitError("限流"), GOOD])
    gateway, _, _ = make_gateway(provider)

    result = await ask(gateway, retry_on_timeout=False)

    assert (result.record.attempts, result.record.retried) == (2, True)


# ---- 输出修复 ----


async def test_invalid_json_is_repaired_by_asking_again() -> None:
    provider = FakeProvider("a", script=["好的，行程如下：武汉两天", GOOD])
    gateway, sleeps, _ = make_gateway(provider)

    result = await ask(gateway)

    assert result.payload == {"city": "武汉", "days": 2}
    assert (result.record.attempts, result.record.retried, result.record.repaired) == (2, False, True)
    assert sleeps.waits == []
    assert (result.record.input_tokens, result.record.output_tokens) == (20, 10)
    # 第二次请求带着原来的问题、模型上一次的输出和哪里不对
    first, second = provider.calls
    assert second[:2] == first
    assert (second[2].role, second[2].content) == ("assistant", "好的，行程如下：武汉两天")
    assert second[3].role == "user" and "不是合法的 JSON" in second[3].content


async def test_output_still_invalid_after_repair_raises_format_error() -> None:
    provider = FakeProvider("a", script=["不是 JSON", "还不是 JSON"])
    gateway, _, records = make_gateway(provider)

    with pytest.raises(LLMOutputFormatError) as error:
        await ask(gateway)

    assert len(provider.calls) == 2  # 只让模型重答一次
    assert error.value.raw_output == "还不是 JSON"
    assert "还不是 JSON" not in str(error.value)
    record = records.items[0]
    assert (record.ok, record.error_code, record.repaired, record.attempts) == (False, "bad_output", True, 2)


async def test_code_fence_is_stripped_without_asking_again() -> None:
    provider = FakeProvider("a", script=[f"```json\n{GOOD}\n```"])
    gateway, _, _ = make_gateway(provider)

    result = await ask(gateway)

    assert result.payload["days"] == 2
    assert (result.record.attempts, result.record.repaired) == (1, False)


async def test_json_array_is_not_accepted() -> None:
    provider = FakeProvider("a", script=["[1, 2]", GOOD])
    gateway, _, _ = make_gateway(provider)

    result = await ask(gateway)

    assert result.record.repaired
    assert "JSON 对象" in provider.calls[1][3].content


async def test_truncated_output_tells_model_to_be_shorter() -> None:
    cut = ProviderReply(text='{"city": "武', model="fake-model-1", finish_reason="length")
    provider = FakeProvider("a", script=[cut, GOOD])
    gateway, _, _ = make_gateway(provider)

    result = await ask(gateway)

    assert result.record.repaired
    assert "截断" in provider.calls[1][3].content


async def test_empty_output_is_repaired() -> None:
    provider = FakeProvider("a", script=["", GOOD])
    gateway, _, _ = make_gateway(provider)

    result = await ask(gateway)

    assert result.record.repaired
    assert provider.calls[1][2].content  # 带回去的上一次输出不能是空字符串


async def test_schema_gives_parsed_object() -> None:
    provider = FakeProvider("a", script=[GOOD])
    gateway, _, _ = make_gateway(provider)

    result = await ask(gateway, schema=Trip)

    assert result.parsed == Trip(city="武汉", days=2)
    assert not result.record.repaired


async def test_schema_violation_is_repaired() -> None:
    provider = FakeProvider("a", script=['{"city": "武汉"}', GOOD])
    gateway, _, _ = make_gateway(provider)

    result = await ask(gateway, schema=Trip)

    assert result.parsed == Trip(city="武汉", days=2)
    assert result.record.repaired
    assert "days" in provider.calls[1][3].content


async def test_retry_and_repair_can_both_happen() -> None:
    provider = FakeProvider("a", script=[LLMUpstreamError("出错"), "不是 JSON", GOOD])
    gateway, _, _ = make_gateway(provider)

    result = await ask(gateway)

    assert (result.record.attempts, result.record.retried, result.record.repaired) == (3, True, True)


# ---- 自动换备用模型（默认关着） ----


async def test_no_fallback_by_default() -> None:
    a, b = FakeProvider("a", script=[LLMAuthError("key 无效")]), FakeProvider("b", script=[GOOD])
    gateway, _, _ = make_gateway(a, b)

    with pytest.raises(LLMAuthError):
        await ask(gateway)
    assert b.calls == []


async def test_fallback_when_turned_on() -> None:
    a, b = FakeProvider("a", script=[LLMAuthError("key 无效")]), FakeProvider("b", script=[GOOD])
    gateway, _, records = make_gateway(a, b, fallback_provider="b")

    result = await ask(gateway)

    assert result.provider == "b"
    # 两个模型各留一条记录，看得出是谁失败、谁回答的
    assert [(record.provider, record.ok) for record in records.items] == [("a", False), ("b", True)]


async def test_chosen_provider_never_falls_back() -> None:
    a, b = FakeProvider("a", script=[LLMAuthError("key 无效")]), FakeProvider("b", script=[GOOD])
    gateway, _, _ = make_gateway(a, b, fallback_provider="b")

    with pytest.raises(LLMAuthError):
        await ask(gateway, provider="a")
    assert b.calls == []


# ---- 记录写不进去 ----


async def test_recorder_failure_does_not_break_the_call() -> None:
    def broken_recorder(record) -> None:
        raise OSError("磁盘满了")

    provider = FakeProvider("a", script=[GOOD])
    gateway = LLMGateway(providers={"a": provider}, default_provider="a", recorder=broken_recorder)

    result = await ask(gateway)

    assert result.payload["city"] == "武汉"
