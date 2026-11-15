"""千问和豆包 provider 的测试。不联网：用 httpx 的 MockTransport 代替对方的服务器。

错误样例里的状态码和错误码取自两家官方错误码文档（2026-11-15 查阅，网址见
app/services/llm/providers.py 开头）；说明文字（message）是为测试写的示意，不是对方的原文，
除非注明。测的是"这个状态码和错误码被翻译成哪种错误"，不是对方真实返回的全部细节。
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.services.llm.base import LLMMessage
from app.services.llm.errors import (
    LLMAuthError,
    LLMBadConfigError,
    LLMBadRequestError,
    LLMContentBlockedError,
    LLMError,
    LLMProviderError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUpstreamError,
)
from app.services.llm.gateway import LLMGateway
from app.services.llm.providers import DoubaoProvider, QwenProvider, build_providers
from tests.llm_fakes import Records, Sleeps

# 测试专用的假 key，不是真的
FAKE_KEY = "sk-test-0123456789abcdef"
MESSAGES = [LLMMessage("system", "只输出 JSON"), LLMMessage("user", "你好")]


def ok_body(content: str = '{"ok": true}', model: str = "qwen-plus") -> dict:
    return {
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 40, "completion_tokens": 11},
    }


def error_body(code: str, message: str = "示意的错误说明") -> dict:
    return {"error": {"code": code, "message": message, "type": code}}


class Server:
    """假的对方服务器：按顺序返回事先排好的回应，并记下收到的请求。"""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self._responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        step = self._responses.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    @property
    def bodies(self) -> list[dict]:
        return [json.loads(request.content) for request in self.requests]


def qwen(server: Server, **overrides) -> QwenProvider:
    options = {
        "api_key": FAKE_KEY,
        "base_url": "https://qwen.test/v1",
        "model": "qwen-plus",
        "transport": httpx.MockTransport(server),
    }
    options.update(overrides)
    return QwenProvider(**options)


def doubao(server: Server, **overrides) -> DoubaoProvider:
    options = {
        "api_key": FAKE_KEY,
        "base_url": "https://doubao.test/api/v3/",
        "model": "ep-test-123",
        "transport": httpx.MockTransport(server),
    }
    options.update(overrides)
    return DoubaoProvider(**options)


async def chat(provider, *, json_mode: bool = True):
    return await provider.chat(messages=MESSAGES, json_mode=json_mode, temperature=0.2, timeout=5, trace_id="t")


# ---- 正常请求 ----


async def test_qwen_request_and_reply() -> None:
    server = Server(httpx.Response(200, json=ok_body()))

    reply = await chat(qwen(server))

    request = server.requests[0]
    assert str(request.url) == "https://qwen.test/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
    body = server.bodies[0]
    assert body["model"] == "qwen-plus"
    assert body["messages"] == [{"role": "system", "content": "只输出 JSON"}, {"role": "user", "content": "你好"}]
    assert body["response_format"] == {"type": "json_object"}
    assert "thinking" not in body
    assert (reply.text, reply.model, reply.finish_reason) == ('{"ok": true}', "qwen-plus", "stop")
    assert (reply.input_tokens, reply.output_tokens) == (40, 11)


async def test_doubao_sends_endpoint_id_and_reports_real_model_name() -> None:
    server = Server(httpx.Response(200, json=ok_body(model="doubao-real-model-name")))

    reply = await chat(doubao(server))

    assert str(server.requests[0].url) == "https://doubao.test/api/v3/chat/completions"
    assert server.bodies[0]["model"] == "ep-test-123"
    assert reply.model == "doubao-real-model-name"


async def test_doubao_thinking_is_only_sent_when_set() -> None:
    default, off = Server(httpx.Response(200, json=ok_body())), Server(httpx.Response(200, json=ok_body()))

    await chat(doubao(default))
    await chat(doubao(off, thinking="disabled"))

    assert "thinking" not in default.bodies[0]
    assert off.bodies[0]["thinking"] == {"type": "disabled"}


async def test_reasoning_content_is_ignored() -> None:
    """开着深度思考时，回答里多一个 reasoning_content。我们只要 content。"""
    body = ok_body(content='{"ok": true}')
    body["choices"][0]["message"]["reasoning_content"] = "用户让我输出 JSON……"
    server = Server(httpx.Response(200, json=body))

    reply = await chat(doubao(server))

    assert reply.text == '{"ok": true}'


async def test_json_mode_can_be_off() -> None:
    server = Server(httpx.Response(200, json=ok_body()))

    await chat(qwen(server), json_mode=False)

    assert "response_format" not in server.bodies[0]


def test_is_configured_needs_key_and_model() -> None:
    server = Server()
    assert qwen(server).is_configured()
    assert not qwen(server, api_key=None).is_configured()
    assert not qwen(server, api_key="   ").is_configured()
    assert not doubao(server, model=None).is_configured()
    assert not doubao(server, model="").is_configured()


# ---- 错误翻译 ----

QWEN_ERRORS = [
    (401, "invalid_api_key", "", LLMAuthError),
    (401, "InvalidApiKey", "", LLMAuthError),
    (403, "AccessDenied", "", LLMAuthError),
    (403, "Model.AccessDenied", "", LLMAuthError),
    (404, "ModelNotFound", "", LLMBadConfigError),
    (404, "model_not_supported", "", LLMBadConfigError),
    (400, "InvalidParameter", "Model not exist.", LLMBadConfigError),  # 说明文字是文档里的原文
    (429, "Throttling.RateQuota", "", LLMRateLimitError),
    (429, "limit_requests", "", LLMRateLimitError),
    (429, "limit_burst_rate", "", LLMRateLimitError),
    (429, "insufficient_quota", "Allocated quota exceeded, please increase your quota limit.", LLMRateLimitError),
    (429, "Throttling.AllocationQuota", "Free allocated quota exceeded.", LLMQuotaError),
    (403, "AllocationQuota.FreeTierOnly", "", LLMQuotaError),
    (400, "Arrearage", "", LLMQuotaError),
    (403, "Arrearage", "", LLMQuotaError),
    (400, "data_inspection_failed", "", LLMContentBlockedError),
    (400, "DataInspectionFailed", "", LLMContentBlockedError),
    (500, "InternalError.DataInspection", "", LLMUpstreamError),  # 审核服务自己坏了，不是内容被拦
    (500, "InternalError", "", LLMUpstreamError),
    (503, "ServiceUnavailable", "", LLMUpstreamError),
    (500, "RequestTimeOut", "", LLMTimeoutError),
    (400, "InvalidParameter", "", LLMBadRequestError),
]

DOUBAO_ERRORS = [
    (401, "AuthenticationError", "", LLMAuthError),
    (401, "InvalidAccountStatus", "", LLMAuthError),
    (403, "AccessDenied", "", LLMAuthError),
    (404, "InvalidEndpointOrModel.NotFound", "", LLMBadConfigError),
    (404, "ModelNotOpen", "", LLMBadConfigError),
    (400, "InvalidEndpoint.ClosedEndpoint", "", LLMBadConfigError),
    (429, "RateLimitExceeded.EndpointRPMExceeded", "", LLMRateLimitError),
    (429, "RateLimitExceeded.EndpointTPMExceeded", "", LLMRateLimitError),
    (429, "ModelAccountRpmRateLimitExceeded", "", LLMRateLimitError),
    (429, "ModelAccountTpmRateLimitExceeded", "", LLMRateLimitError),
    (429, "RequestBurstTooFast", "", LLMRateLimitError),
    (429, "ServerOverloaded", "", LLMRateLimitError),
    (429, "QuotaExceeded", "", LLMQuotaError),
    (429, "SetLimitExceeded", "", LLMQuotaError),
    (429, "AccountQuotaExceeded", "", LLMQuotaError),
    (429, "ModelAccountTpdRateLimitExceeded", "", LLMQuotaError),
    (403, "AccountOverdueError", "", LLMQuotaError),
    (400, "SensitiveContentDetected", "", LLMContentBlockedError),
    (400, "InputTextSensitiveContentDetected", "", LLMContentBlockedError),
    (400, "OutputTextSensitiveContentDetected", "", LLMContentBlockedError),
    (400, "InputTextRiskDetection", "", LLMContentBlockedError),
    (408, "RequestTimeout", "", LLMTimeoutError),
    (500, "InternalServiceError", "", LLMUpstreamError),
    (503, "NoAvailableService", "", LLMUpstreamError),
    (400, "InvalidParameter", "", LLMBadRequestError),
    (400, "MissingParameter", "", LLMBadRequestError),
]


@pytest.mark.parametrize(("status", "code", "message", "expected"), QWEN_ERRORS)
async def test_qwen_error_mapping(status: int, code: str, message: str, expected: type[LLMError]) -> None:
    server = Server(httpx.Response(status, json=error_body(code, message or "示意的错误说明")))

    with pytest.raises(LLMError) as error:
        await chat(qwen(server))

    assert type(error.value) is expected
    assert error.value.provider == "qwen"
    assert f"HTTP {status}" in str(error.value) and code in str(error.value)


@pytest.mark.parametrize(("status", "code", "message", "expected"), DOUBAO_ERRORS)
async def test_doubao_error_mapping(status: int, code: str, message: str, expected: type[LLMError]) -> None:
    server = Server(httpx.Response(status, json=error_body(code, message or "示意的错误说明")))

    with pytest.raises(LLMError) as error:
        await chat(doubao(server))

    assert type(error.value) is expected
    assert error.value.provider == "doubao"


def test_only_some_errors_are_retryable() -> None:
    retryable = {LLMTimeoutError, LLMRateLimitError, LLMUpstreamError}
    for kind in {expected for *_, expected in QWEN_ERRORS + DOUBAO_ERRORS}:
        assert kind.retryable == (kind in retryable), kind.__name__


async def test_error_without_json_body_falls_back_to_status() -> None:
    server = Server(httpx.Response(502, text="<html>Bad Gateway</html>"))

    with pytest.raises(LLMUpstreamError):
        await chat(qwen(server))


async def test_rate_limit_reads_retry_after_header() -> None:
    with_header = Server(httpx.Response(429, json=error_body("limit_requests"), headers={"retry-after": "7"}))
    without = Server(httpx.Response(429, json=error_body("limit_requests")))
    with_date = Server(
        httpx.Response(429, json=error_body("limit_requests"), headers={"retry-after": "Sun, 15 Nov 2026 12:00:00 GMT"})
    )

    waits = []
    for server in (with_header, without, with_date):
        with pytest.raises(LLMRateLimitError) as error:
            await chat(qwen(server))
        waits.append(error.value.retry_after)

    assert waits == [7.0, None, None]


async def test_timeout_and_network_errors() -> None:
    with pytest.raises(LLMTimeoutError):
        await chat(qwen(Server(httpx.ReadTimeout("读超时"))))
    with pytest.raises(LLMUpstreamError):
        await chat(qwen(Server(httpx.ConnectError("连不上"))))


@pytest.mark.parametrize("body", [{}, {"choices": []}, {"choices": [{"message": None}]}, "不是 JSON"])
async def test_unexpected_reply_shape_is_provider_error(body) -> None:
    response = httpx.Response(200, text=body) if isinstance(body, str) else httpx.Response(200, json=body)

    with pytest.raises(LLMProviderError):
        await chat(doubao(Server(response)))


# ---- 不支持 JSON 输出模式的模型 ----


async def test_falls_back_to_prompt_only_when_json_mode_is_rejected() -> None:
    """说明文字是为测试写的：真实的报错原文还没见过，判断依据是 400 的说明里提到 response_format。"""
    rejected = httpx.Response(400, json=error_body("InvalidParameter", "response_format is not supported by this model"))
    server = Server(rejected, httpx.Response(200, json=ok_body()), httpx.Response(200, json=ok_body()))
    provider = doubao(server)

    first = await chat(provider)
    await chat(provider)

    assert first.text == '{"ok": true}'
    assert "response_format" in server.bodies[0]
    assert "response_format" not in server.bodies[1]
    # 记住了：之后的请求不再带这个参数，也不用再试一次
    assert "response_format" not in server.bodies[2]
    assert len(server.requests) == 3


async def test_other_bad_requests_are_not_resent() -> None:
    server = Server(httpx.Response(400, json=error_body("InvalidParameter", "temperature 超出范围")))

    with pytest.raises(LLMBadRequestError):
        await chat(doubao(server))

    assert len(server.requests) == 1


# ---- key 不能漏出去 ----


async def test_key_is_removed_from_error_messages() -> None:
    echo = httpx.Response(401, json=error_body("invalid_api_key", f"Incorrect API key provided: {FAKE_KEY}"))
    other = httpx.Response(401, json=error_body("invalid_api_key", "Bearer abcdefghijklmnop is not valid"))

    for response in (echo, other):
        with pytest.raises(LLMAuthError) as error:
            await chat(qwen(Server(response)))
        text = str(error.value)
        assert FAKE_KEY not in text and "abcdefghijklmnop" not in text
        assert "***" in text


async def test_key_is_not_in_any_error_or_repr() -> None:
    steps = [
        httpx.ReadTimeout(f"timeout {FAKE_KEY}"),
        httpx.ConnectError(f"connect {FAKE_KEY}"),
        httpx.Response(500, text=f"server error {FAKE_KEY}"),
        httpx.Response(200, text=f"not json {FAKE_KEY}"),
    ]
    for step in steps:
        provider = qwen(Server(step))
        with pytest.raises(LLMError) as error:
            await chat(provider)
        assert FAKE_KEY not in str(error.value)
        assert FAKE_KEY not in repr(error.value)
        assert FAKE_KEY not in repr(provider)
        assert FAKE_KEY not in str(vars(provider).get("model"))


async def test_long_upstream_message_is_cut_short() -> None:
    server = Server(httpx.Response(400, json=error_body("InvalidParameter", "很长的说明" * 200)))

    with pytest.raises(LLMBadRequestError) as error:
        await chat(doubao(server))

    assert len(str(error.value)) < 400


# ---- 网关和真实 provider 类接在一起 ----


async def test_gateway_retries_rate_limit_then_succeeds() -> None:
    server = Server(
        httpx.Response(429, json=error_body("RateLimitExceeded.EndpointRPMExceeded"), headers={"retry-after": "3"}),
        httpx.Response(200, json=ok_body(content='{"city": "武汉"}', model="doubao-real-model-name")),
    )
    sleeps, records = Sleeps(), Records()
    gateway = LLMGateway(
        providers={"doubao": doubao(server)}, default_provider="doubao", sleep=sleeps, recorder=records
    )

    result = await gateway.complete_json(task="test", system_prompt="你是测试助手。", user_prompt="你好")

    assert result.payload == {"city": "武汉"}
    assert sleeps.waits == [3.0]
    record = records.items[0]
    assert (record.provider, record.model, record.attempts, record.retried) == (
        "doubao",
        "doubao-real-model-name",
        2,
        True,
    )


async def test_gateway_does_not_retry_quota_errors() -> None:
    server = Server(httpx.Response(429, json=error_body("SetLimitExceeded")))
    sleeps = Sleeps()
    gateway = LLMGateway(providers={"doubao": doubao(server)}, default_provider="doubao", sleep=sleeps)

    with pytest.raises(LLMQuotaError):
        await gateway.complete_json(task="test", system_prompt="你是测试助手。", user_prompt="你好")

    assert len(server.requests) == 1 and sleeps.waits == []


# ---- 按设置建 provider ----


def test_build_providers_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        qwen_api_key=FAKE_KEY,
        doubao_api_key=FAKE_KEY,
        doubao_model="ep-test-123",
        doubao_thinking="Disabled",
    )

    providers = build_providers(settings)

    assert list(providers) == ["qwen", "doubao"]
    assert providers["qwen"].is_configured() and providers["qwen"].model == "qwen-plus"
    assert providers["doubao"].is_configured() and providers["doubao"].thinking == "disabled"


def test_build_providers_without_keys_is_not_configured() -> None:
    providers = build_providers(Settings(_env_file=None, qwen_api_key=None, doubao_api_key=None, doubao_model=None))

    assert not providers["qwen"].is_configured()
    assert not providers["doubao"].is_configured()
    assert providers["doubao"].thinking is None


def test_build_providers_rejects_unknown_thinking_value() -> None:
    with pytest.raises(ValueError, match="DOUBAO_THINKING"):
        build_providers(Settings(_env_file=None, doubao_thinking="auto"))
