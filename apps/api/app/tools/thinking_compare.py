"""用真实的规划请求，比较豆包开着和关着深度思考的效果（板块 4 留下的事）。

用法（在 Mac 终端）：
    cd ~/WuhanMemory-project2 && corepack pnpm plan:thinking
    cd ~/WuhanMemory-project2 && corepack pnpm plan:thinking -- --repeat 2 --timeout 120

每条请求分别在"开着思考""关着思考"下跑一遍完整的规划链路（抽偏好、排行程、查交通、校验、必要时修正一次），
和网站用的是同一条路，只是对话和行程存进一个临时数据库，不进网站的数据库。
这是真实调用：会花豆包的 token，路线查询先用 SQLite 里的高德缓存，缓存里没有的会调用高德。
每次模型调用照常在 llm_calls 表里留一条记录（task 是 extract_preferences / generate_itinerary / repair_itinerary）。

打印的每一个数字都是这次跑出来的，不写死。只打印模型名、耗时、token 和校验结果，不打印 key 和提示词。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import AsyncIterator

from app.services.llm.base import LLMCallRecord
from app.services.llm.errors import LLMError
from app.services.planning.pipeline import PlanningPipeline

# 用户会说的真实规划请求。都给了天数和日期，免得被反问。日期取在跑脚本时之后的日子。
PROMPTS: tuple[str, ...] = (
    "武汉两天，喜欢历史和美食，坐地铁，{d1} 出发",
    "{d1} 带爸妈在武汉轻松玩一天，他们走不了太多路，可以打车",
    "武汉三天，{d1} 到，想拍照、看老建筑和江边夜景，节奏紧凑一点",
)
MODES: tuple[str, ...] = ("enabled", "disabled")
MODE_LABELS = {"enabled": "开着思考", "disabled": "关着思考"}


@dataclass
class RunResult:
    prompt_no: int
    mode: str
    seconds: float
    kind: str | None = None  # question / itinerary / failed；出错时为 None
    error: str | None = None
    rounds: int | None = None
    first_errors: int | None = None
    status: str | None = None
    errors: int | None = None
    warnings: int | None = None
    error_codes: list[str] = field(default_factory=list)
    calls: list[LLMCallRecord] = field(default_factory=list)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens or 0 for c in self.calls)

    @property
    def input_tokens(self) -> int:
        return sum(c.input_tokens or 0 for c in self.calls)

    @property
    def model(self) -> str | None:
        return next((c.model for c in self.calls if c.model), None)


# make(mode) 给出这个模式下的规划链路和它的调用记录列表
Make = Callable[[str], AbstractAsyncContextManager[tuple[PlanningPipeline, list[LLMCallRecord]]]]


async def run_one(pipeline: PlanningPipeline, records: list[LLMCallRecord], prompt: str, prompt_no: int, mode: str) -> RunResult:
    before = len(records)
    conv = pipeline.conversations.create()
    pipeline.conversations.add_message(conv.id, "user", prompt)
    started = perf_counter()
    result = RunResult(prompt_no=prompt_no, mode=mode, seconds=0)
    try:
        outcome = await pipeline.handle(conv.id, prompt, provider="doubao")
    except LLMError as exc:
        result.error = f"{exc.code}：{exc.message}"
    else:
        result.kind = outcome.kind
        if outcome.version is not None:
            v = outcome.version
            result.rounds = v.planner.rounds
            result.first_errors = v.planner.firstRoundErrors
            result.status = v.validation.status
            result.errors = len(v.validation.errors)
            result.warnings = len(v.validation.warnings)
            result.error_codes = [i.code for i in v.validation.errors]
    result.seconds = perf_counter() - started
    result.calls = records[before:]
    return result


async def run_all(make: Make, prompts: list[str], repeat: int, out: Callable[[str], None] = print) -> list[RunResult]:
    results: list[RunResult] = []
    for n, prompt in enumerate(prompts, start=1):
        for r in range(repeat):
            # 两种模式交替跑，免得网络或服务端状况的变化都落在同一种模式上
            modes = MODES if r % 2 == 0 else tuple(reversed(MODES))
            for mode in modes:
                async with make(mode) as (pipeline, records):
                    res = await run_one(pipeline, records, prompt, n, mode)
                results.append(res)
                out(_line(res))
    return results


def _line(r: RunResult) -> str:
    head = f"请求 {r.prompt_no} · {MODE_LABELS[r.mode]} · {r.seconds:.1f} 秒"
    if r.error:
        return f"{head} · 出错 {r.error}"
    if r.kind == "question":
        return f"{head} · 模型没抽到天数或日期，被反问了"
    calls = "、".join(f"{c.task}{'(失败)' if not c.ok else ''} {c.latency_ms / 1000:.1f}s" for c in r.calls)
    extra = f" · 第一版错误 {r.first_errors} 处，修正过" if r.rounds == 2 else ""
    codes = f"（{'、'.join(r.error_codes)}）" if r.error_codes else ""
    return (
        f"{head} · 校验 {r.status}，错误 {r.errors}{codes}，警告 {r.warnings}{extra}"
        f" · 输出 token {r.output_tokens} · {calls}"
    )


def summarize(results: list[RunResult], out: Callable[[str], None] = print) -> None:
    out("")
    out("== 汇总（每种模式各跑了几次，就按几次算） ==")
    for mode in MODES:
        rs = [r for r in results if r.mode == mode]
        if not rs:
            continue
        done = [r for r in rs if r.error is None and r.kind != "question"]
        avg = lambda xs: sum(xs) / len(xs) if xs else 0.0  # noqa: E731
        out(f"{MODE_LABELS[mode]}：跑了 {len(rs)} 次")
        out(f"  出错 {sum(1 for r in rs if r.error)} 次，被反问 {sum(1 for r in rs if r.kind == 'question')} 次")
        if done:
            out(
                f"  校验：通过 {sum(r.status == 'passed' for r in done)}，有警告 {sum(r.status == 'warning' for r in done)}，"
                f"未通过 {sum(r.status == 'failed' for r in done)}"
            )
            out(f"  第一版就没有错误的 {sum(r.first_errors == 0 for r in done)} 次，需要修正的 {sum(r.rounds == 2 for r in done)} 次")
            out(f"  平均耗时 {avg([r.seconds for r in done]):.1f} 秒（整条链路，含查交通）")
            out(f"  平均输出 token {avg([r.output_tokens for r in done]):.0f}，平均输入 token {avg([r.input_tokens for r in done]):.0f}")
        models = sorted({r.model for r in rs if r.model})
        if models:
            out(f"  模型名：{'、'.join(models)}")


def _prompts(today_iso: str) -> list[str]:
    from datetime import date, timedelta

    d1 = date.fromisoformat(today_iso) + timedelta(days=7)
    return [p.format(d1=d1.isoformat()) for p in PROMPTS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="比较豆包开着和关着深度思考时的规划效果（真实调用）")
    parser.add_argument("--repeat", type=int, default=1, help="每条请求在每种模式下跑几次，默认 1")
    parser.add_argument("--timeout", type=int, default=None, help="每次模型调用的超时秒数，默认用 .env 里的设置")
    args = parser.parse_args(argv)

    # 放在这里才 import：要读 .env
    import httpx

    from app.core.config import settings
    from app.data_quality.rules import today_in_city
    from app.repositories.conversation_repository import SqliteConversationRepository
    from app.repositories.itinerary_repository import SqliteItineraryRepository
    from app.repositories.llm_call_repository import SqliteLLMCallRepository
    from app.repositories.poi_repository import SqlitePoiRepository
    from app.repositories.route_cache_repository import SqliteRouteCacheRepository
    from app.services.llm.factory import build_gateway
    from app.services.routing.amap import AmapRouteProvider
    from app.services.routing.service import RouteService

    timeout = args.timeout or settings.llm_request_timeout_seconds
    scratch = Path(tempfile.mkdtemp(prefix="thinking-compare-")) / "compare.db"
    calls_db = SqliteLLMCallRepository(settings.database_path)

    @asynccontextmanager
    async def make(mode: str) -> AsyncIterator[tuple[PlanningPipeline, list[LLMCallRecord]]]:
        records: list[LLMCallRecord] = []

        def record(r: LLMCallRecord) -> None:
            records.append(r)
            calls_db.add(r)

        config = settings.model_copy(update={"doubao_thinking": mode, "llm_request_timeout_seconds": timeout})
        gateway = build_gateway(config, recorder=record)
        async with httpx.AsyncClient() as client:
            pois = SqlitePoiRepository(settings.database_path)
            routes = RouteService(
                pois,
                AmapRouteProvider(settings.amap_web_service_key, settings.amap_base_url, client),
                SqliteRouteCacheRepository(settings.database_path),
            )
            yield (
                PlanningPipeline(
                    gateway=gateway,
                    pois=pois,
                    routes=routes,
                    itineraries=SqliteItineraryRepository(scratch),
                    conversations=SqliteConversationRepository(scratch),
                    today=today_in_city,
                ),
                records,
            )

    if not settings.doubao_api_key or not settings.doubao_model:
        print("豆包还没配置：apps/api/.env 里缺 DOUBAO_API_KEY 或 DOUBAO_MODEL。")
        return 1
    prompts = _prompts(today_in_city().isoformat())
    print(f"每次模型调用超时 {timeout} 秒，最多重试 {settings.llm_max_retries} 次；每条请求每种模式跑 {args.repeat} 次")
    for n, p in enumerate(prompts, start=1):
        print(f"请求 {n}：{p}")
    print("")
    results = asyncio.run(run_all(make, prompts, args.repeat))
    summarize(results)
    return 0 if all(r.error is None for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
