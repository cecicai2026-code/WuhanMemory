"""模型接口的测试。网关换成用假 provider 建的，不联网。"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.llm.errors import LLMAuthError, LLMRateLimitError, LLMUpstreamError
from app.services.llm.factory import get_llm_gateway
from app.services.llm.gateway import LLMGateway
from tests.llm_fakes import FakeProvider, Records, Sleeps, Slow

GREETING = '{"reply": "欢迎来武汉"}'


class Setup:
    def __init__(self, gateway: LLMGateway, records: Records, client: TestClient) -> None:
        self.gateway, self.records, self.client = gateway, records, client


@pytest.fixture
def use_gateway() -> Iterator:
    def install(*providers: FakeProvider, default: str = "qwen", **options) -> Setup:
        records = Records()
        gateway = LLMGateway(
            providers={provider.name: provider for provider in providers},
            default_provider=default,
            recorder=records,
            sleep=Sleeps(),
            **options,
        )
        app.dependency_overrides[get_llm_gateway] = lambda: gateway
        return Setup(gateway, records, TestClient(app))

    yield install
    app.dependency_overrides.pop(get_llm_gateway, None)


def fake(name: str, label: str, **options) -> FakeProvider:
    provider = FakeProvider(name, **options)
    provider.label = label
    return provider


def test_providers_lists_both_models(use_gateway) -> None:
    setup = use_gateway(fake("qwen", "通义千问"), fake("doubao", "豆包", configured=False, model="ep-secret-endpoint"))

    response = setup.client.get("/api/llm/providers")

    assert response.status_code == 200
    assert response.json() == {
        "defaultProvider": "qwen",
        "providers": [
            {"id": "qwen", "label": "通义千问", "configured": True, "isDefault": True},
            {"id": "doubao", "label": "豆包", "configured": False, "isDefault": False},
        ],
    }
    # 接入点 ID 不给前端
    assert "ep-secret-endpoint" not in response.text


def test_providers_with_unknown_default(use_gateway) -> None:
    setup = use_gateway(fake("qwen", "通义千问"), fake("doubao", "豆包"), default="mock")

    body = setup.client.get("/api/llm/providers").json()

    assert body["defaultProvider"] is None
    assert not any(provider["isDefault"] for provider in body["providers"])


def test_listing_providers_does_not_call_any_model(use_gateway) -> None:
    qwen = fake("qwen", "通义千问")
    setup = use_gateway(qwen)

    setup.client.get("/api/llm/providers")

    assert qwen.calls == [] and setup.records.items == []


def test_ping_uses_default_model(use_gateway) -> None:
    qwen, doubao = fake("qwen", "通义千问", script=[GREETING]), fake("doubao", "豆包", script=[GREETING])
    setup = use_gateway(qwen, doubao)

    response = setup.client.post("/api/llm/ping", json={})

    assert response.status_code == 200
    body = response.json()
    assert (body["provider"], body["label"], body["model"]) == ("qwen", "通义千问", "fake-model-1")
    assert body["reply"] == "欢迎来武汉"
    assert (body["attempts"], body["retried"], body["repaired"]) == (1, False, False)
    assert body["latencyMs"] >= 0
    assert doubao.calls == []
    assert [(record.task, record.provider) for record in setup.records.items] == [("ping", "qwen")]


def test_ping_can_choose_model(use_gateway) -> None:
    qwen, doubao = fake("qwen", "通义千问", script=[GREETING]), fake("doubao", "豆包", script=[GREETING])
    setup = use_gateway(qwen, doubao)

    body = setup.client.post("/api/llm/ping", json={"provider": "doubao"}).json()

    assert (body["provider"], body["label"]) == ("doubao", "豆包")
    assert qwen.calls == []


def test_ping_reports_retry_and_repair(use_gateway) -> None:
    setup = use_gateway(fake("qwen", "通义千问", script=[LLMUpstreamError("出错"), "你好呀", GREETING]))

    body = setup.client.post("/api/llm/ping", json={}).json()

    assert (body["attempts"], body["retried"], body["repaired"]) == (3, True, True)


@pytest.mark.parametrize(
    ("provider", "script", "status", "code", "retryable"),
    [
        ("gpt", [], 400, "unknown_provider", False),
        ("doubao", [], 503, "not_configured", False),
        ("qwen", [LLMAuthError("key 无效")], 502, "invalid_key", False),
        ("qwen", [LLMRateLimitError("限流")], 429, "rate_limited", True),
        ("qwen", [Slow(1.0)], 504, "timeout", True),
        ("qwen", ["不是 JSON", "还不是"], 502, "bad_output", False),
    ],
)
def test_ping_errors(use_gateway, provider, script, status, code, retryable) -> None:
    setup = use_gateway(
        fake("qwen", "通义千问", script=script),
        fake("doubao", "豆包", configured=False),
        max_retries=0,
        timeout_seconds=0.05,
    )

    response = setup.client.post("/api/llm/ping", json={"provider": provider})

    assert response.status_code == status
    detail = response.json()["detail"]
    assert (detail["code"], detail["retryable"]) == (code, retryable)
    assert detail["message"]
