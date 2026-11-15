"""LLMGateway：业务代码调用大模型的唯一入口。

一次 `complete_json` 做这几件事：
1. 选模型：请求里指定了就用指定的，没指定用 .env 里的默认模型。
2. 发请求：超过规定时间算超时。
3. 出错时：超时、限流、对方服务器出错、网络断开会再试，其余的错直接报。
   限流时先等一会儿：对方说了等多久就等多久（有上限），没说就按 1 秒、2 秒递增。
4. 检查输出：必须是一个 JSON 对象；给了 schema 的话还要通过 schema 校验。
   不合格就把问题告诉模型，让它重答一次；还不合格就报"输出格式错"。
5. 记录：不管成功失败，都留一条记录（哪个模型、耗时、是否重试过、是否修复过输出）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app.services.llm.base import (
    LLMCallRecord,
    LLMJsonResult,
    LLMMessage,
    LLMProvider,
    ProviderInfo,
    ProviderReply,
)
from app.services.llm.errors import (
    LLMError,
    LLMNotConfiguredError,
    LLMOutputFormatError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnknownProviderError,
)

logger = logging.getLogger("wuhanmemory.llm")

# 加在每次请求的系统提示词后面。两个模型用同一句，对比才公平；
# 千问的 JSON 输出模式还要求提示词里出现"JSON"这个词。
JSON_ONLY_INSTRUCTION = "只输出一个 JSON 对象，不要输出解释、前后缀或 Markdown 代码块。"

# 让模型重答时，把它上一次的输出带回去，太长就截掉后面的
_MAX_ECHO_CHARS = 6000

_CODE_FENCE = re.compile(r"^```[a-zA-Z]*\s*\n(.*?)\n?```$", re.DOTALL)

Recorder = Callable[[LLMCallRecord], None]
Sleep = Callable[[float], Awaitable[None]]


class _OutputProblem(Exception):
    """模型的输出不合格。description 会写进让模型重答的那条消息里。"""

    def __init__(self, description: str) -> None:
        super().__init__(description)
        self.description = description


@dataclass
class _CallStats:
    attempts: int = 0
    retried: bool = False
    repaired: bool = False
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def add_usage(self, reply: ProviderReply) -> None:
        self.model = reply.model or self.model
        if reply.input_tokens is not None:
            self.input_tokens = (self.input_tokens or 0) + reply.input_tokens
        if reply.output_tokens is not None:
            self.output_tokens = (self.output_tokens or 0) + reply.output_tokens


def _log_record(record: LLMCallRecord) -> None:
    logger.info(
        "llm 调用 task=%s provider=%s model=%s 耗时=%dms 请求次数=%d 重试=%s 修复=%s 结果=%s",
        record.task,
        record.provider,
        record.model,
        record.latency_ms,
        record.attempts,
        record.retried,
        record.repaired,
        "成功" if record.ok else record.error_code,
    )


class LLMGateway:
    def __init__(
        self,
        *,
        providers: Mapping[str, LLMProvider],
        default_provider: str,
        timeout_seconds: float = 60,
        max_retries: int = 2,
        fallback_provider: str | None = None,
        backoff_seconds: float = 1.0,
        max_rate_limit_wait_seconds: float = 20.0,
        recorder: Recorder | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._providers = dict(providers)
        self.default_provider = default_provider
        # 默认不开。开了以后，只有"没指定模型"的请求在默认模型失败时才会换到这个模型
        self.fallback_provider = fallback_provider or None
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.backoff_seconds = backoff_seconds
        self.max_rate_limit_wait_seconds = max_rate_limit_wait_seconds
        self._recorder = recorder
        self._sleep = sleep

    # ---- 有哪些模型 ----

    def providers(self) -> list[ProviderInfo]:
        return [
            ProviderInfo(
                id=name,
                label=provider.label,
                configured=provider.is_configured(),
                model=provider.model,
                is_default=name == self.default_provider,
            )
            for name, provider in self._providers.items()
        ]

    def _resolve(self, name: str | None) -> LLMProvider:
        chosen = name or self.default_provider
        provider = self._providers.get(chosen)
        if provider is None:
            options = "、".join(self._providers)
            source = "请求里指定的模型" if name else "默认模型（LLM_PROVIDER）"
            raise LLMUnknownProviderError(f"{source} {chosen!r} 不在可用的模型里，可选：{options}")
        return provider

    # ---- 调用 ----

    async def complete_json(
        self,
        *,
        task: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel] | None = None,
        provider: str | None = None,
        temperature: float = 0.2,
        retry_on_timeout: bool = True,
    ) -> LLMJsonResult:
        """让模型回答一个 JSON 对象。

        task 是这次调用的用途（比如 "extract_preferences"），只用于记录。
        provider 不填就用默认模型。schema 填了的话，输出还要通过它的校验。
        retry_on_timeout=False 时超时不重试，直接报错（2026-11-15 Cecilia 定的：排行程这种慢请求，
        超时再试一般也是超时，重试两次要让用户白等 3 分钟）；限流、对方出错照样重试。
        """
        chosen = self._resolve(provider)
        try:
            return await self._run(chosen, task, system_prompt, user_prompt, schema, temperature, retry_on_timeout)
        except LLMError:
            fallback = self._fallback_for(explicit=provider is not None, failed=chosen)
            if fallback is None:
                raise
            logger.warning("llm %s 失败，换用备用模型 %s", chosen.name, fallback.name)
            return await self._run(fallback, task, system_prompt, user_prompt, schema, temperature, retry_on_timeout)

    def _fallback_for(self, *, explicit: bool, failed: LLMProvider) -> LLMProvider | None:
        if explicit or not self.fallback_provider or self.fallback_provider == failed.name:
            return None
        return self._providers.get(self.fallback_provider)

    async def _run(
        self,
        provider: LLMProvider,
        task: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel] | None,
        temperature: float,
        retry_on_timeout: bool = True,
    ) -> LLMJsonResult:
        trace_id = uuid4().hex
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        stats = _CallStats(model=provider.model)

        def finish(error_code: str | None) -> LLMCallRecord:
            record = LLMCallRecord(
                trace_id=trace_id,
                task=task,
                provider=provider.name,
                model=stats.model,
                started_at=started_at.isoformat(timespec="seconds"),
                latency_ms=round((perf_counter() - started) * 1000),
                attempts=stats.attempts,
                retried=stats.retried,
                repaired=stats.repaired,
                ok=error_code is None,
                error_code=error_code,
                input_tokens=stats.input_tokens,
                output_tokens=stats.output_tokens,
            )
            _log_record(record)
            if self._recorder is not None:
                try:
                    self._recorder(record)
                except Exception as exc:  # 记录写不进去不能让这次调用失败
                    logger.warning("llm 调用记录没有写成功：%s", type(exc).__name__)
            return record

        try:
            if not provider.is_configured():
                raise LLMNotConfiguredError(
                    f"{provider.label}还没有配置：apps/api/.env 里缺 key 或模型名", provider=provider.name
                )

            messages = [
                LLMMessage("system", f"{system_prompt.rstrip()}\n\n{JSON_ONLY_INSTRUCTION}"),
                LLMMessage("user", user_prompt),
            ]
            reply = await self._chat_with_retry(provider, messages, temperature, trace_id, stats, retry_on_timeout)
            try:
                payload, parsed = _parse_output(reply, schema)
            except _OutputProblem as problem:
                # 输出不合格：把问题告诉模型，让它重答一次
                stats.repaired = True
                repair_messages = [
                    *messages,
                    LLMMessage("assistant", reply.text[:_MAX_ECHO_CHARS] or "（空）"),
                    LLMMessage(
                        "user",
                        f"你上一次的输出不能用：{problem.description}。"
                        f"请重新回答原来的问题。{JSON_ONLY_INSTRUCTION}",
                    ),
                ]
                reply = await self._chat_with_retry(provider, repair_messages, temperature, trace_id, stats, retry_on_timeout)
                try:
                    payload, parsed = _parse_output(reply, schema)
                except _OutputProblem as second:
                    raise LLMOutputFormatError(
                        f"{provider.label}重答一次后输出仍然不合格：{second.description}",
                        provider=provider.name,
                        raw_output=reply.text,
                    ) from None
        except LLMError as exc:
            finish(exc.code)
            raise

        record = finish(None)
        return LLMJsonResult(
            provider=provider.name,
            model=stats.model or "",
            payload=payload,
            parsed=parsed,
            record=record,
        )

    async def _chat_with_retry(
        self,
        provider: LLMProvider,
        messages: list[LLMMessage],
        temperature: float,
        trace_id: str,
        stats: _CallStats,
        retry_on_timeout: bool = True,
    ) -> ProviderReply:
        attempt = 0
        while True:
            stats.attempts += 1
            try:
                reply = await self._chat_once(provider, messages, temperature, trace_id)
            except LLMError as exc:
                if not exc.retryable or attempt >= self.max_retries:
                    raise
                if isinstance(exc, LLMTimeoutError) and not retry_on_timeout:
                    raise
                wait = self._wait_seconds(exc, attempt)
                logger.warning(
                    "llm %s 第 %d 次请求失败（%s），%.1f 秒后重试", provider.name, stats.attempts, exc.code, wait
                )
                stats.retried = True
                await self._sleep(wait)
                attempt += 1
                continue
            stats.add_usage(reply)
            return reply

    async def _chat_once(
        self,
        provider: LLMProvider,
        messages: list[LLMMessage],
        temperature: float,
        trace_id: str,
    ) -> ProviderReply:
        try:
            return await asyncio.wait_for(
                provider.chat(
                    messages=messages,
                    json_mode=True,
                    temperature=temperature,
                    timeout=self.timeout_seconds,
                    trace_id=trace_id,
                ),
                timeout=self.timeout_seconds,
            )
        except LLMError:
            raise
        except TimeoutError:
            raise LLMTimeoutError(
                f"{provider.label}在 {self.timeout_seconds:g} 秒内没有回答", provider=provider.name
            ) from None
        except Exception as exc:
            # 只记异常的类型，不记它的内容，免得把请求里的东西带进日志
            raise LLMProviderError(
                f"{provider.label}调用出错（{type(exc).__name__}）", provider=provider.name
            ) from None

    def _wait_seconds(self, exc: LLMError, attempt: int) -> float:
        backoff = self.backoff_seconds * (2**attempt)
        if isinstance(exc, LLMRateLimitError):
            wait = exc.retry_after if exc.retry_after is not None else backoff
            return min(max(wait, 0.0), self.max_rate_limit_wait_seconds)
        return backoff


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    match = _CODE_FENCE.match(text)
    return match.group(1).strip() if match else text


def _parse_output(reply: ProviderReply, schema: type[BaseModel] | None) -> tuple[dict[str, Any], BaseModel | None]:
    text = _strip_code_fence(reply.text)
    if not text:
        raise _OutputProblem("输出是空的")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        if reply.finish_reason == "length":
            raise _OutputProblem("输出太长，在中途被截断了，请写得更简短") from None
        raise _OutputProblem(f"不是合法的 JSON（第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}）") from None
    if not isinstance(data, dict):
        raise _OutputProblem("最外层必须是一个 JSON 对象")
    if schema is None:
        return data, None
    try:
        parsed = schema.model_validate(data)
    except ValidationError as exc:
        details = "；".join(
            f"{'.'.join(str(part) for part in error['loc']) or '最外层'}: {error['msg']}"
            for error in exc.errors(include_url=False, include_input=False)[:8]
        )
        raise _OutputProblem(f"JSON 的字段不符合要求（{details}）") from None
    return data, parsed
