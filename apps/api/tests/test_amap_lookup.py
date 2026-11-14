"""高德地点搜索脚本的测试。不联网：用假的高德响应（虚构的名称和坐标）测解析和结果文件。"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.tools.amap_lookup import AmapError, parse_candidates, parse_target, run

FAKE_OK = {
    "status": "1",
    "info": "OK",
    "pois": [
        {"id": "B0TEST1", "name": "测试点一", "adname": "测试区", "address": "测试路 1 号", "type": "风景名胜", "location": "114.30,30.55"},
        # 高德没有地址时返回 []
        {"id": "B0TEST2", "name": "测试点二", "adname": "测试区", "address": [], "type": "风景名胜", "location": "116.40,39.90"},
        {"id": "B0TEST3", "name": "没有坐标", "adname": "", "address": "", "type": "", "location": []},
    ],
}


def test_parse_candidates() -> None:
    cs = parse_candidates(FAKE_OK, limit=5)
    assert [c.name for c in cs] == ["测试点一", "测试点二"]
    assert cs[0].lng == 114.30 and cs[0].coordSystem == "GCJ-02" and cs[0].inWuhan
    assert cs[1].address == "" and not cs[1].inWuhan


def test_parse_error() -> None:
    with pytest.raises(AmapError, match="INVALID_USER_KEY"):
        parse_candidates({"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}, limit=3)


def test_parse_target() -> None:
    assert parse_target("test-place=测试景点") == ("test-place", "测试景点")
    with pytest.raises(Exception):
        parse_target("没有等号")


def test_run_writes_record_without_key(tmp_path: Path) -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json=FAKE_OK)

    client = httpx.Client(base_url="https://amap.test", transport=httpx.MockTransport(handler))
    record, path = run([("test-place", "测试景点")], key="SECRET-TEST-KEY", out_dir=tmp_path, client=client, sleep=lambda s: None)

    assert seen["keywords"] == "测试景点" and seen["citylimit"] == "true" and seen["city"] == "420100"
    assert record["source"]["type"] == "amap"
    assert len(record["results"][0]["candidates"]) == 2
    saved = path.read_text(encoding="utf-8")
    assert "SECRET-TEST-KEY" not in saved
    assert json.loads(saved)["results"][0]["id"] == "test-place"


def test_run_keeps_going_after_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["keywords"] == "坏的":
            return httpx.Response(200, json={"status": "0", "info": "DAILY_QUERY_OVER_LIMIT"})
        return httpx.Response(200, json=FAKE_OK)

    client = httpx.Client(base_url="https://amap.test", transport=httpx.MockTransport(handler))
    record, _ = run([("a", "坏的"), ("b", "好的")], key="k", out_dir=tmp_path, client=client, sleep=lambda s: None)
    assert "DAILY_QUERY_OVER_LIMIT" in record["results"][0]["error"]
    assert record["results"][1]["error"] is None


def test_retries_once_on_qps_limit(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json={"status": "0", "info": "CUQPS_HAS_EXCEEDED_THE_LIMIT", "infocode": "10021"})
        return httpx.Response(200, json=FAKE_OK)

    client = httpx.Client(base_url="https://amap.test", transport=httpx.MockTransport(handler))
    waits: list[float] = []
    record, _ = run([("a", "测试")], key="k", out_dir=tmp_path, client=client, sleep=waits.append)
    assert calls["n"] == 2 and waits == [2.0]
    assert record["results"][0]["error"] is None
