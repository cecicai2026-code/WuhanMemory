"""网关和 provider 之间、网关和业务代码之间传递的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class LLMMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class ProviderReply:
    """provider 发一次请求拿到的回答。"""

    text: str
    # 对方返回的真实模型名。豆包请求里填的是 endpoint ID，这里才是模型名
    model: str
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMProvider(Protocol):
    """一家模型服务。只负责发一次请求、把对方的错误翻译成 errors.py 里的类型。

    重试、等待、输出修复、记录都在网关里做，所以每家 provider 都很薄，
    测试里也可以用一个假的 provider 代替。
    """

    name: str
    label: str
    model: str | None

    def is_configured(self) -> bool:
        ...

    async def chat(
        self,
        *,
        messages: list[LLMMessage],
        json_mode: bool,
        temperature: float,
        timeout: float,
        trace_id: str,
    ) -> ProviderReply:
        ...


@dataclass(frozen=True)
class LLMCallRecord:
    """一次网关调用的记录。板块 6 的双模型对比要用。

    一次网关调用可能向模型发了好几次请求（重试、让模型重答），attempts 是总次数。
    """

    trace_id: str
    task: str
    provider: str
    model: str | None
    started_at: str
    latency_ms: int
    attempts: int
    retried: bool
    repaired: bool
    ok: bool
    error_code: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class LLMJsonResult:
    provider: str
    model: str
    payload: dict[str, Any]
    # 调用时给了 schema 的话，这里是校验通过的对象
    parsed: BaseModel | None
    record: LLMCallRecord


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    label: str
    configured: bool
    model: str | None
    is_default: bool
