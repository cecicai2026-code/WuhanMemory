"""高德安全密钥代理的测试。不联网：用 httpx.MockTransport 假装高德，检查转发地址和 jscode。"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.amap_proxy import get_proxy_client
from app.core.config import Settings, get_settings
from app.main import app

SECRET = "test-security-code"
PAGE = "http://localhost:3000"


def make_client(settings: Settings, seen: list[httpx.Request], fail: bool = False) -> TestClient:
    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if fail:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={"status": "1", "info": "OK"}, headers={"content-type": "application/json"})

    async def fake_client():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            yield c

    app.dependency_overrides[get_proxy_client] = fake_client
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()


def settings(**kw) -> Settings:
    return Settings(_env_file=None, amap_security_js_code=SECRET, cors_origins=[PAGE], **kw)


def test_forwards_to_restapi_with_jscode() -> None:
    seen: list[httpx.Request] = []
    c = make_client(settings(), seen)
    r = c.get("/_AMapService/v3/place/text?key=jskey&keywords=%E9%BB%84%E9%B9%A4%E6%A5%BC", headers={"referer": PAGE + "/map"})
    assert r.status_code == 200 and r.json()["info"] == "OK"
    assert len(seen) == 1
    url = seen[0].url
    assert url.host == "restapi.amap.com" and url.path == "/v3/place/text"
    assert url.params["key"] == "jskey" and url.params["keywords"] == "黄鹤楼"
    assert url.params["jscode"] == SECRET
    # 安全密钥不会回到浏览器
    assert SECRET not in r.text


def test_styles_go_to_webapi() -> None:
    seen: list[httpx.Request] = []
    c = make_client(settings(), seen)
    c.get("/_AMapService/v4/map/styles?styleid=abc", headers={"origin": PAGE})
    assert seen[0].url.host == "webapi.amap.com" and seen[0].url.path == "/v4/map/styles"


def test_browser_cannot_override_jscode() -> None:
    seen: list[httpx.Request] = []
    c = make_client(settings(), seen)
    c.get("/_AMapService/v3/x?jscode=fake", headers={"referer": PAGE + "/"})
    assert seen[0].url.params.get_list("jscode") == [SECRET]


def test_rejects_other_sites() -> None:
    seen: list[httpx.Request] = []
    c = make_client(settings(), seen)
    assert c.get("/_AMapService/v3/x", headers={"referer": "https://evil.example/"}).status_code == 403
    assert c.get("/_AMapService/v3/x").status_code == 403
    assert seen == []


def test_missing_security_code() -> None:
    seen: list[httpx.Request] = []
    c = make_client(Settings(_env_file=None, amap_security_js_code=None, cors_origins=[PAGE]), seen)
    r = c.get("/_AMapService/v3/x", headers={"referer": PAGE})
    assert r.status_code == 503 and r.json()["code"] == "amap-security-missing"
    assert seen == []


def test_upstream_unreachable() -> None:
    seen: list[httpx.Request] = []
    c = make_client(settings(), seen, fail=True)
    r = c.get("/_AMapService/v3/x", headers={"referer": PAGE})
    assert r.status_code == 502 and r.json()["code"] == "amap-unreachable"
