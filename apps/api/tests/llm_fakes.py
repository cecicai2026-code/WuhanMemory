"""测试用的假 provider。不联网，按事先排好的剧本一步一步回应。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.services.llm.base import LLMCallRecord, LLMMessage, ProviderReply


@dataclass
class Slow:
    """剧本里的一步：先等 seconds 秒，再回答 text。用来测超时。"""

    seconds: float
    text: str = '{"ok": true}'


class FakeProvider:
    """剧本里的每一步可以是：
    - 字符串：当作模型的回答
    - ProviderReply：完整的回答（可以带 finish_reason、token 数）
    - 异常：这一次请求抛出它
    - Slow：等一会儿再回答
    剧本用完了还被调用，说明网关多发了请求，直接报错。
    """

    def __init__(
        self,
        name: str = "fake",
        *,
        script: list[Any] | None = None,
        configured: bool = True,
        model: str = "fake-model-1",
    ) -> None:
        self.name = name
        self.label = f"假模型 {name}"
        self.model: str | None = model
        self._configured = configured
        self._script = list(script or [])
        self.calls: list[list[LLMMessage]] = []

    def is_configured(self) -> bool:
        return self._configured

    async def chat(
        self,
        *,
        messages: list[LLMMessage],
        json_mode: bool,
        temperature: float,
        timeout: float,
        trace_id: str,
    ) -> ProviderReply:
        self.calls.append(list(messages))
        if not self._script:
            raise AssertionError(f"{self.name} 的剧本用完了，网关多发了一次请求")
        step = self._script.pop(0)
        if isinstance(step, BaseException):
            raise step
        if isinstance(step, Slow):
            await asyncio.sleep(step.seconds)
            step = step.text
        if isinstance(step, ProviderReply):
            return step
        return ProviderReply(text=step, model=self.model or "", finish_reason="stop", input_tokens=10, output_tokens=5)


class Sleeps:
    """代替 asyncio.sleep：只记下网关想等多久，不真的等。"""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


class Records:
    """代替调用记录的存储：把每条记录收进列表。"""

    def __init__(self) -> None:
        self.items: list[LLMCallRecord] = []

    def __call__(self, record: LLMCallRecord) -> None:
        self.items.append(record)
