"""模型接口的测试。网关换成用假 provider 建的，不联网。"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.llm.factory import get_llm_gateway
from app.services.llm.gateway import LLMGateway
from tests.llm_fakes import FakeProvider, Records, Sleeps

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


def test_ping_is_gone(use_gateway) -> None:
    """临时的试一句在板块 5 接上对话后去掉了。"""
    setup = use_gateway(fake("qwen", "通义千问"))
    assert setup.client.post("/api/llm/ping", json={}).status_code in (404, 405)
