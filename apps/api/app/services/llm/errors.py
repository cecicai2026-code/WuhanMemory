"""网关的错误类型。

业务代码只需要认这里的类型，不用知道千问或豆包各自返回什么状态码和错误码。
`code` 给程序和调用记录用；`retryable` 告诉网关这种错值不值得再试一次。

错误信息里不能出现 key：provider 把对方返回的内容放进信息之前要先遮掉 key。
"""

from __future__ import annotations


class LLMError(Exception):
    code = "llm_error"
    retryable = False

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider


class LLMUnknownProviderError(LLMError):
    """请求里指定的模型（或 .env 里的默认模型）不在网关的清单里。"""

    code = "unknown_provider"


class LLMNotConfiguredError(LLMError):
    """没配 key，或者没填模型名（豆包是 endpoint ID）。"""

    code = "not_configured"


class LLMAuthError(LLMError):
    """key 无效，或者这个 key 没有权限用这个模型。"""

    code = "invalid_key"


class LLMBadConfigError(LLMError):
    """key 是对的，但模型名或豆包的接入点填错了。"""

    code = "bad_config"


class LLMTimeoutError(LLMError):
    """在规定时间内没有等到回答。"""

    code = "timeout"
    retryable = True


class LLMRateLimitError(LLMError):
    """被限流。retry_after 是对方要求等的秒数，没给就是 None。"""

    code = "rate_limited"
    retryable = True

    def __init__(self, message: str, *, provider: str | None = None, retry_after: float | None = None) -> None:
        super().__init__(message, provider=provider)
        self.retry_after = retry_after


class LLMUpstreamError(LLMError):
    """对方服务器出错（5xx）或者网络断了。"""

    code = "upstream_error"
    retryable = True


class LLMContentBlockedError(LLMError):
    """请求或回答被对方的内容审核拦下。"""

    code = "content_blocked"


class LLMBadRequestError(LLMError):
    """对方认为请求本身有问题（其他 4xx）。再发一次也一样，所以不重试。"""

    code = "bad_request"


class LLMProviderError(LLMError):
    """provider 代码里出了没预料到的错，比如对方返回的结构变了。"""

    code = "provider_error"


class LLMOutputFormatError(LLMError):
    """让模型重答一次之后，输出仍然不是合格的 JSON。

    raw_output 留着最后一次的原文，方便调试；它不会被放进错误信息。
    """

    code = "bad_output"

    def __init__(self, message: str, *, provider: str | None = None, raw_output: str = "") -> None:
        super().__init__(message, provider=provider)
        self.raw_output = raw_output
