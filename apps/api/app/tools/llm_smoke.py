"""冒烟测试：给千问和豆包各发同一条简单请求，看真实接口通不通。

用法（在 Mac 终端）：
    cd ~/WuhanMemory-project2 && corepack pnpm llm:smoke

这是真实调用，会花一点点 token，所以不放在单元测试里。请求经过 LLMGateway，
和网站用的是同一条路；每次调用会在 SQLite 的 llm_calls 表里留一条 task=smoke 的记录。
只打印模型名、耗时和回答，不打印 key。两个模型都成功时退出码是 0，否则是 1。
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from time import perf_counter

from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.llm.errors import LLMError
from app.services.llm.gateway import LLMGateway

SYSTEM_PROMPT = "你是地理常识助手。"
USER_PROMPT = '武汉是哪个省的省会？按这个格式回答：{"province": "省的名字"}'


class _Answer(BaseModel):
    province: str = Field(min_length=1, max_length=20)


async def run(gateway: LLMGateway, out: Callable[[str], None] = print) -> int:
    """给每个模型发一次请求，打印结果。返回没通过的模型个数。"""
    out(f"请求：{USER_PROMPT}")
    failed = 0
    for info in gateway.providers():
        out("")
        out(f"== {info.label}（{info.id}）" + ("  ← 默认模型" if info.is_default else ""))
        if not info.configured:
            out("  结果：没有配置，跳过（apps/api/.env 里缺 key 或模型名）")
            failed += 1
            continue

        started = perf_counter()
        try:
            result = await gateway.complete_json(
                task="smoke",
                system_prompt=SYSTEM_PROMPT,
                user_prompt=USER_PROMPT,
                schema=_Answer,
                provider=info.id,
            )
        except LLMError as exc:
            out(f"  结果：失败（{exc.code}）")
            out(f"  耗时：{(perf_counter() - started) * 1000:.0f} ms")
            out(f"  说明：{exc.message}")
            failed += 1
            continue

        record = result.record
        out("  结果：成功")
        out(f"  模型名：{result.model}")
        out(f"  耗时：{record.latency_ms} ms")
        out(
            f"  请求次数：{record.attempts}（重试：{'有' if record.retried else '没有'}，"
            f"修复输出：{'有' if record.repaired else '没有'}）"
        )
        out(f"  token：输入 {record.input_tokens}，输出 {record.output_tokens}")
        out(f"  回答：{result.payload}")

    out("")
    total = len(gateway.providers())
    out(f"汇总：{total - failed} / {total} 个模型通过")
    return failed


def main() -> int:
    # 放在这里才 import：建网关要读 .env，出错时给一句看得懂的话
    from app.services.llm.factory import get_llm_gateway

    try:
        gateway = get_llm_gateway()
    except ValueError as exc:
        print(f".env 里的设置有问题：{exc}")
        return 1
    print(f"超时 {settings.llm_request_timeout_seconds} 秒，最多重试 {settings.llm_max_retries} 次")
    print(f"豆包深度思考（DOUBAO_THINKING）：{settings.doubao_thinking.strip() or '没填，用模型自己的默认值'}")
    failed = asyncio.run(run(gateway))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
