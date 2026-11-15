"""模型接口返回的数据结构。前端类型在 packages/shared/src/llm.ts，两边要一致。

字段说明见 docs/architecture/api-contracts.md 的"模型"一节。
"""

from __future__ import annotations

from pydantic import BaseModel


class LLMProviderOut(BaseModel):
    id: str
    label: str
    # key 和模型名（豆包是接入点 ID）都填了才算已配置。这里只说有没有，不返回 key 和接入点 ID
    configured: bool
    isDefault: bool


class LLMProvidersOut(BaseModel):
    # .env 里 LLM_PROVIDER 指的模型；填的不是可用的模型时是 None
    defaultProvider: str | None
    providers: list[LLMProviderOut]


class LLMErrorOut(BaseModel):
    code: str
    message: str
    retryable: bool
    provider: str | None = None
