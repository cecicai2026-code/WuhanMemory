"""千问和豆包的 provider。两家都走 OpenAI 兼容接口（/chat/completions）。

provider 只做两件事：发一次请求；把对方的错误翻译成 errors.py 里的类型。
重试、等待、输出修复都在网关里。

key 只出现在请求头里。放进错误信息的对方返回内容，先经过 _redact 遮掉 key。
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.core.config import Settings
from app.services.llm.base import LLMMessage, ProviderReply
from app.services.llm.errors import (
    LLMAuthError,
    LLMBadConfigError,
    LLMBadRequestError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUpstreamError,
)

_KEY_LIKE = re.compile(r"(sk-|Bearer\s+)[A-Za-z0-9._\-]{6,}")
_MAX_DETAIL_CHARS = 200


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        name: str,
        label: str,
        api_key: str | None,
        base_url: str,
        model: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.name = name
        self.label = label
        self._api_key = (api_key or "").strip() or None
        self.base_url = base_url.rstrip("/")
        self.model = (model or "").strip() or None
        # 测试里传一个假的 transport，就不会真的联网
        self._transport = transport

    def __repr__(self) -> str:  # 不让 key 出现在 repr 里
        return f"<{type(self).__name__} {self.name} model={self.model!r}>"

    def is_configured(self) -> bool:
        return bool(self._api_key and self.model)

    def _redact(self, text: str) -> str:
        if self._api_key:
            text = text.replace(self._api_key, "***")
        return _KEY_LIKE.sub(r"\1***", text)

    def _request_body(self, messages: list[LLMMessage], json_mode: bool, temperature: float) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    async def chat(
        self,
        *,
        messages: list[LLMMessage],
        json_mode: bool,
        temperature: float,
        timeout: float,
        trace_id: str,
    ) -> ProviderReply:
        body = self._request_body(messages, json_mode, temperature)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "authorization": f"Bearer {self._api_key}",
                        "content-type": "application/json",
                    },
                    json=body,
                )
        except httpx.TimeoutException:
            raise LLMTimeoutError(f"{self.label}在 {timeout:g} 秒内没有回答", provider=self.name) from None
        except httpx.HTTPError as exc:
            raise LLMUpstreamError(
                f"连不上{self.label}（{type(exc).__name__}）", provider=self.name
            ) from None

        if response.status_code != 200:
            raise self._error_from_response(response)

        try:
            data = response.json()
            choice = data["choices"][0]
            usage = data.get("usage") or {}
            return ProviderReply(
                text=choice["message"].get("content") or "",
                model=data.get("model") or self.model or "",
                finish_reason=choice.get("finish_reason"),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise LLMProviderError(f"{self.label}返回的内容看不懂（结构和预期不一样）", provider=self.name) from None

    # ---- 把对方的错误翻译成我们的类型 ----

    def _error_detail(self, response: httpx.Response) -> tuple[str, str]:
        """取出对方的错误码和说明（已遮掉 key、截短）。"""
        code, message = "", ""
        try:
            error = response.json().get("error") or {}
            code = str(error.get("code") or error.get("type") or "")
            message = str(error.get("message") or "")
        except (ValueError, AttributeError):
            message = response.text
        return self._redact(code)[:80], self._redact(message)[:_MAX_DETAIL_CHARS]

    def _error_from_response(self, response: httpx.Response) -> LLMError:
        status = response.status_code
        code, message = self._error_detail(response)
        detail = f"HTTP {status}" + (f"，{code}" if code else "") + (f"：{message}" if message else "")

        if status in (401, 403):
            return LLMAuthError(f"{self.label}的 key 无效或没有权限（{detail}）", provider=self.name)
        if status == 404:
            return LLMBadConfigError(f"{self.label}找不到这个模型或接入点（{detail}）", provider=self.name)
        if status == 429:
            return LLMRateLimitError(
                f"{self.label}限流（{detail}）",
                provider=self.name,
                retry_after=_retry_after_seconds(response),
            )
        if status >= 500:
            return LLMUpstreamError(f"{self.label}服务器出错（{detail}）", provider=self.name)
        return LLMBadRequestError(f"{self.label}拒绝了这次请求（{detail}）", provider=self.name)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None  # 也可能是一个日期，这种情况按没给处理


def build_providers(settings: Settings) -> dict[str, OpenAICompatibleProvider]:
    return {
        "qwen": OpenAICompatibleProvider(
            name="qwen",
            label="通义千问",
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            model=settings.qwen_model,
        ),
        "doubao": OpenAICompatibleProvider(
            name="doubao",
            label="豆包",
            api_key=settings.doubao_api_key,
            base_url=settings.doubao_base_url,
            model=settings.doubao_model,
        ),
    }
