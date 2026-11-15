"""用高德地点搜索查景点坐标，给 Cecilia 核对后填进景点资料。

用法（在 apps/api 目录下，需要 .env 里的 AMAP_WEB_SERVICE_KEY）：
    python -m app.tools.amap_lookup yellow-crane-tower=黄鹤楼 hubu-alley=户部巷

每个参数写成"景点id=搜索词"。脚本在武汉市范围内按关键字搜索，每个景点列出前几个结果：
名称、所在区、地址、坐标（GCJ-02），以及坐标在不在武汉范围内。
结果同时存到 data/amap-lookup/<日期>.json（不进 git），Claude 从这个文件读取。

这里查到的坐标在景点资料里标 verification: "placeholder"、来源类型 "amap"，
界面上显示"待确认"。Cecilia 在高德地图上看过点位没问题后，改成 "confirmed"。

只调用高德的"关键字搜索"接口（/v3/place/text），每个景点一次请求。key 不会打印也不会写进结果文件。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.data_quality.rules import CITY_TZ, WUHAN_BOUNDS

SEARCH_PATH = "/v3/place/text"
# 武汉市的行政区划代码
WUHAN_ADCODE = "420100"
# 高德个人开发者的 key 每秒能发的请求数很少，两次请求之间停一下；超限时再等一会儿重试一次
REQUEST_GAP_SECONDS = 0.5
QPS_RETRY_SECONDS = 2.0
QPS_LIMIT_CODES = ("CUQPS_HAS_EXCEEDED_THE_LIMIT", "10021")


class AmapError(Exception):
    pass


@dataclass
class Candidate:
    amapId: str
    name: str
    district: str
    address: str
    type: str
    lng: float
    lat: float
    coordSystem: str
    inWuhan: bool


def _text(v: Any) -> str:
    # 高德在没有值时会返回空数组 []，不是空字符串
    return v if isinstance(v, str) else ""


def parse_candidates(payload: dict[str, Any], limit: int) -> list[Candidate]:
    if payload.get("status") != "1":
        raise AmapError(f"高德返回错误：{payload.get('info', '未知错误')}（{payload.get('infocode', '')}）")
    out: list[Candidate] = []
    for poi in payload.get("pois", [])[:limit]:
        loc = _text(poi.get("location"))
        if "," not in loc:
            continue
        lng, lat = (float(x) for x in loc.split(",", 1))
        b = WUHAN_BOUNDS
        out.append(
            Candidate(
                amapId=_text(poi.get("id")),
                name=_text(poi.get("name")),
                district=_text(poi.get("adname")),
                address=_text(poi.get("address")),
                type=_text(poi.get("type")),
                lng=lng,
                lat=lat,
                coordSystem="GCJ-02",
                inWuhan=b["min_lng"] <= lng <= b["max_lng"] and b["min_lat"] <= lat <= b["max_lat"],
            )
        )
    return out


def search(client: httpx.Client, key: str, keyword: str, limit: int) -> list[Candidate]:
    res = client.get(
        SEARCH_PATH,
        params={
            "key": key,
            "keywords": keyword,
            "city": WUHAN_ADCODE,
            "citylimit": "true",
            "offset": str(limit),
            "page": "1",
            "extensions": "base",
            "output": "json",
        },
    )
    res.raise_for_status()
    return parse_candidates(res.json(), limit)


def parse_target(arg: str) -> tuple[str, str]:
    if "=" not in arg:
        raise argparse.ArgumentTypeError(f"「{arg}」要写成 景点id=搜索词，例如 yellow-crane-tower=黄鹤楼")
    poi_id, keyword = arg.split("=", 1)
    if not poi_id or not keyword:
        raise argparse.ArgumentTypeError(f"「{arg}」的 id 或搜索词是空的")
    return poi_id.strip(), keyword.strip()


def run(
    targets: list[tuple[str, str]],
    *,
    key: str,
    out_dir: Path,
    limit: int = 3,
    client: httpx.Client | None = None,
    sleep=time.sleep,
) -> tuple[dict[str, Any], Path]:
    now = datetime.now(CITY_TZ)
    owns_client = client is None
    client = client or httpx.Client(base_url=settings.amap_base_url, timeout=15)
    results = []
    try:
        for i, (poi_id, keyword) in enumerate(targets):
            if i:
                sleep(REQUEST_GAP_SECONDS)
            candidates, error = [], None
            for attempt in range(2):
                try:
                    candidates, error = [asdict(c) for c in search(client, key, keyword, limit)], None
                    break
                except (AmapError, httpx.HTTPError) as err:
                    candidates, error = [], str(err)
                    if attempt == 0 and any(code in error for code in QPS_LIMIT_CODES):
                        sleep(QPS_RETRY_SECONDS)
                        continue
                    break
            results.append({"id": poi_id, "keyword": keyword, "candidates": candidates, "error": error})
    finally:
        if owns_client:
            client.close()

    record = {
        "source": {
            "type": "amap",
            "title": "高德开放平台 地点搜索（关键字搜索 /v3/place/text）",
            "url": "https://lbs.amap.com/api/webservice/guide/api/search",
            "accessedAt": now.date().isoformat(),
        },
        "fetchedAt": now.isoformat(timespec="seconds"),
        "city": WUHAN_ADCODE,
        "results": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{now:%Y-%m-%d-%H%M%S}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record, path


def format_record(record: dict[str, Any]) -> str:
    lines = []
    for r in record["results"]:
        lines.append(f"{r['id']}（搜索：{r['keyword']}）")
        if r["error"]:
            lines.append(f"  出错：{r['error']}")
        elif not r["candidates"]:
            lines.append("  没有搜到")
        for i, c in enumerate(r["candidates"], 1):
            flag = "" if c["inWuhan"] else "  ← 不在武汉范围内"
            lines.append(f"  {i}. {c['name']}｜{c['district']}｜{c['address'] or '无地址'}｜{c['lng']},{c['lat']}{flag}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用高德地点搜索查景点坐标")
    parser.add_argument("targets", nargs="+", type=parse_target, help="景点id=搜索词")
    parser.add_argument("--limit", type=int, default=3, help="每个景点列出几个结果，默认 3")
    parser.add_argument("--out-dir", type=Path, default=settings.data_dir / "amap-lookup")
    args = parser.parse_args(argv)

    key = settings.amap_web_service_key
    if not key:
        print("apps/api/.env 里没有 AMAP_WEB_SERVICE_KEY，先填好再运行。")
        return 1

    record, path = run(args.targets, key=key, out_dir=args.out_dir, limit=args.limit)
    print(format_record(record))
    print(f"结果已存到 {path}")
    failed = [r["id"] for r in record["results"] if r["error"]]
    return 1 if failed and len(failed) == len(record["results"]) else 0


if __name__ == "__main__":
    sys.exit(main())
