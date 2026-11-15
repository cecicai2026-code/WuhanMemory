"""千问和豆包的 provider。两家都走 OpenAI 兼容接口（/chat/completions）。

provider 只做两件事：发一次请求；把对方的错误翻译成 errors.py 里的类型。
重试、等待、输出修复都在网关里。

两家不一样的地方都收在各自的类里（QwenProvider、DoubaoProvider）：
- 错误码不同。对照表按两家官方错误码文档写（2026-11-15 查阅）：
  千问 https://help.aliyun.com/zh/model-studio/error-code
  豆包 https://www.volcengine.com/docs/82379/1299023
- 豆包请求里的 model 填的是接入点 ID（ep- 开头），返回里的 model 才是真实模型名。
- 豆包有深度思考开关（请求参数 thinking），千问的 qwen-plus 默认不思考。

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
    LLMContentBlockedError,
    LLMError,
    LLMProviderError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUpstreamError,
)

_KEY_LIKE = re.compile(r"(sk-|Bearer\s+)[A-Za-z0-9._\-]{6,}")
_MAX_DETAIL_CHARS = 200

# 每种错误对用户怎么说。{label} 是模型的中文名，{detail} 是对方返回的状态码、错误码和说明
_ERROR_TEXT: dict[type[LLMError], str] = {
    LLMAuthError: "{label}的 key 无效或没有权限（{detail}）",
    LLMBadConfigError: "{label}找不到这个模型或接入点，请检查 .env 里的模型名（{detail}）",
    LLMQuotaError: "{label}的额度用完了或账户欠费（{detail}）",
    LLMRateLimitError: "{label}限流（{detail}）",
    LLMContentBlockedError: "{label}的内容审核拦下了这次请求（{detail}）",
    LLMTimeoutError: "{label}处理超时（{detail}）",
    LLMUpstreamError: "{label}服务器出错（{detail}）",
    LLMBadRequestError: "{label}拒绝了这次请求（{detail}）",
}


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
        # 对方明确说不支持 JSON 输出模式之后改成 False，以后只靠提示词要求 JSON
        self._json_mode_supported = True

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
        if json_mode and self._json_mode_supported:
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
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await self._post(client, messages, json_mode, temperature)
                if self._rejects_json_mode(response) and json_mode and self._json_mode_supported:
                    # 这个模型不支持 JSON 输出模式：记下来，去掉这个参数再发一次。
                    # 网关的提示词里本来就要求只输出 JSON，输出不合格还有"重答一次"兜底。
                    self._json_mode_supported = False
                    response = await self._post(client, messages, json_mode, temperature)
        except httpx.TimeoutException:
            raise LLMTimeoutError(f"{self.label}在 {timeout:g} 秒内没有回答", provider=self.name) from None
        except httpx.HTTPError as exc:
            raise LLMUpstreamError(f"连不上{self.label}（{type(exc).__name__}）", provider=self.name) from None

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

    async def _post(
        self, client: httpx.AsyncClient, messages: list[LLMMessage], json_mode: bool, temperature: float
    ) -> httpx.Response:
        return await client.post(
            f"{self.base_url}/chat/completions",
            headers={"authorization": f"Bearer {self._api_key}", "content-type": "application/json"},
            json=self._request_body(messages, json_mode, temperature),
        )

    def _rejects_json_mode(self, response: httpx.Response) -> bool:
        """对方是不是在说"不支持 response_format"。

        两家文档都没给这种情况一个专门的错误码，只能看 400 的说明里有没有提到这个参数。
        """
        if response.status_code != 400:
            return False
        _, message = self._error_detail(response)
        lowered = message.lower()
        return "response_format" in lowered or "json_object" in lowered or "json mode" in lowered

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

    def _classify_by_code(self, status: int, code: str, message: str) -> type[LLMError] | None:
        """各家按自己的错误码判断。判断不了返回 None，交给下面按状态码的通用规则。"""
        return None

    def _classify(self, status: int, code: str, message: str) -> type[LLMError]:
        specific = self._classify_by_code(status, code, message)
        if specific is not None:
            return specific
        if status in (401, 403):
            return LLMAuthError
        if status == 404:
            return LLMBadConfigError
        if status == 408:
            return LLMTimeoutError
        if status == 429:
            return LLMRateLimitError
        if status >= 500:
            return LLMUpstreamError
        return LLMBadRequestError

    def _error_from_response(self, response: httpx.Response) -> LLMError:
        status = response.status_code
        code, message = self._error_detail(response)
        detail = f"HTTP {status}" + (f"，{code}" if code else "") + (f"：{message}" if message else "")
        kind = self._classify(status, code, message)
        text = _ERROR_TEXT[kind].format(label=self.label, detail=detail)
        if kind is LLMRateLimitError:
            return LLMRateLimitError(text, provider=self.name, retry_after=_retry_after_seconds(response))
        return kind(text, provider=self.name)


class QwenProvider(OpenAICompatibleProvider):
    """通义千问（阿里云百炼）。

    同一种错误，百炼有两种写法的错误码（InvalidApiKey / invalid_api_key），所以比较前先去掉
    大小写、点和下划线的差别。
    """

    # 欠费、免费额度用完、预算用完：再试也没用
    _QUOTA_CODES = {
        "arrearage",
        "accountoverdue",
        "allocationquotafreetieronly",
        "prepaidbilloverdue",
        "postpaidbilloverdue",
        "budgetlimitexceeded",
    }

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="qwen", label="通义千问", **kwargs)

    def _classify_by_code(self, status: int, code: str, message: str) -> type[LLMError] | None:
        key = re.sub(r"[._\-]", "", code).lower()
        text = message.lower()
        if key == "invalidapikey":
            return LLMAuthError
        if key in self._QUOTA_CODES:
            return LLMQuotaError
        if status == 429 and ("free" in text or "billing" in text):
            # insufficient_quota 这个错误码既用于"每分钟用量超限"，也用于"免费额度用完"，只能看说明
            return LLMQuotaError
        if "datainspection" in key and status < 500:
            return LLMContentBlockedError
        if key in ("modelnotfound", "modelnotsupported") or "model not exist" in text:
            return LLMBadConfigError
        if key == "requesttimeout":
            return LLMTimeoutError
        return None


class DoubaoProvider(OpenAICompatibleProvider):
    """豆包（火山方舟）。

    thinking 是深度思考开关："enabled" 强制思考，"disabled" 不思考，
    None 表示请求里不带这个参数，用模型自己的默认值。
    """

    # 429 里这几种不是"太快了"，而是额度用完，再试也没用
    _QUOTA_CODES_429 = ("QuotaExceeded", "AccountQuotaExceeded", "SetLimitExceeded", "ModelAccountTpdRateLimitExceeded")

    def __init__(self, *, thinking: str | None = None, **kwargs: Any) -> None:
        super().__init__(name="doubao", label="豆包", **kwargs)
        self.thinking = thinking

    def _request_body(self, messages: list[LLMMessage], json_mode: bool, temperature: float) -> dict[str, Any]:
        body = super()._request_body(messages, json_mode, temperature)
        if self.thinking:
            body["thinking"] = {"type": self.thinking}
        return body

    def _classify_by_code(self, status: int, code: str, message: str) -> type[LLMError] | None:
        if "SensitiveContentDetected" in code or "RiskDetection" in code:
            return LLMContentBlockedError
        if code == "AccountOverdueError" or code.startswith("QuotaExceeded"):
            return LLMQuotaError
        if status == 429 and code.startswith(self._QUOTA_CODES_429):
            return LLMQuotaError
        if code.startswith("InvalidEndpoint") or code == "ModelNotOpen":
            return LLMBadConfigError
        return None


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None  # 也可能是一个日期，这种情况按没给处理


def build_providers(settings: Settings) -> dict[str, OpenAICompatibleProvider]:
    thinking = settings.doubao_thinking.strip().lower()
    if thinking not in ("", "enabled", "disabled"):
        raise ValueError(f"DOUBAO_THINKING 只能留空、填 enabled 或 disabled，现在是 {thinking!r}")
    return {
        "qwen": QwenProvider(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            model=settings.qwen_model,
        ),
        "doubao": DoubaoProvider(
            api_key=settings.doubao_api_key,
            base_url=settings.doubao_base_url,
            model=settings.doubao_model,
            thinking=thinking or None,
        ),
    }
