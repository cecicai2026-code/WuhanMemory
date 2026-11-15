"""模型接口：有哪些模型可以选；选一个模型试一句。

业务代码和接口都只通过 LLMGateway 调用模型，这里不直接碰千问或豆包的接口。
key 只在后端，接口不返回 key，也不返回豆包的接入点 ID。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.schemas.llm import LLMErrorOut, LLMPingOut, LLMPingRequest, LLMProviderOut, LLMProvidersOut
from app.services.llm.errors import LLMError
from app.services.llm.factory import get_llm_gateway
from app.services.llm.gateway import LLMGateway

router = APIRouter(prefix="/api/llm", tags=["llm"])

Gateway = Annotated[LLMGateway, Depends(get_llm_gateway)]

# 每种错误对应的 HTTP 状态码。没列出来的（key 无效、对方出错、输出格式错等）都是 502：
# 我们自己的服务没问题，是后面的模型服务没给出能用的结果。
_STATUS_BY_CODE = {
    "unknown_provider": 400,
    "not_configured": 503,
    "rate_limited": 429,
    "timeout": 504,
}


def llm_http_error(exc: LLMError) -> HTTPException:
    """把网关的错误变成接口的错误回应。板块 5 的规划接口也用这个。"""
    detail = LLMErrorOut(code=exc.code, message=exc.message, retryable=exc.retryable, provider=exc.provider)
    return HTTPException(status_code=_STATUS_BY_CODE.get(exc.code, 502), detail=detail.model_dump())


@router.get("/providers", response_model=LLMProvidersOut)
async def list_providers(gateway: Gateway) -> LLMProvidersOut:
    providers = [
        LLMProviderOut(id=info.id, label=info.label, configured=info.configured, isDefault=info.is_default)
        for info in gateway.providers()
    ]
    default = next((provider.id for provider in providers if provider.isDefault), None)
    return LLMProvidersOut(defaultProvider=default, providers=providers)


class _PingAnswer(BaseModel):
    reply: str = Field(min_length=1, max_length=200)


PING_SYSTEM_PROMPT = "你是 WuhanMemory 的连通性测试助手。"
PING_USER_PROMPT = '用一句不超过二十个字的话问候来武汉旅游的人。按这个格式回答：{"reply": "问候的话"}'


@router.post("/ping", response_model=LLMPingOut)
async def ping(request: LLMPingRequest, gateway: Gateway) -> LLMPingOut:
    """临时接口（板块 4）：给选中的模型发一句固定的话，用来在界面上看到切换确实生效。

    板块 5 接上对话后去掉。每点一次都是一次真实调用。
    """
    try:
        result = await gateway.complete_json(
            task="ping",
            system_prompt=PING_SYSTEM_PROMPT,
            user_prompt=PING_USER_PROMPT,
            schema=_PingAnswer,
            provider=request.provider,
        )
    except LLMError as exc:
        raise llm_http_error(exc) from None

    labels = {info.id: info.label for info in gateway.providers()}
    record = result.record
    return LLMPingOut(
        provider=result.provider,
        label=labels.get(result.provider, result.provider),
        model=result.model,
        reply=result.parsed.reply,  # type: ignore[union-attr]
        latencyMs=record.latency_ms,
        attempts=record.attempts,
        retried=record.retried,
        repaired=record.repaired,
    )
