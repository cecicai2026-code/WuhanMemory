"""模型接口：有哪些模型可以选。

业务代码和接口都只通过 LLMGateway 调用模型，这里不直接碰千问或豆包的接口。
key 只在后端，接口不返回 key，也不返回豆包的接入点 ID。

板块 4 的临时接口 POST /api/llm/ping（试一句）在板块 5 接上对话后去掉了；
选中的模型现在跟着每条对话消息发给后端（POST /api/conversations/{id}/messages 的 provider）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.llm import LLMProvidersOut, LLMProviderOut
from app.services.llm.factory import get_llm_gateway
from app.services.llm.gateway import LLMGateway

router = APIRouter(prefix="/api/llm", tags=["llm"])

Gateway = Annotated[LLMGateway, Depends(get_llm_gateway)]


@router.get("/providers", response_model=LLMProvidersOut)
async def list_providers(gateway: Gateway) -> LLMProvidersOut:
    providers = [
        LLMProviderOut(id=info.id, label=info.label, configured=info.configured, isDefault=info.is_default)
        for info in gateway.providers()
    ]
    default = next((provider.id for provider in providers if provider.isDefault), None)
    return LLMProvidersOut(defaultProvider=default, providers=providers)
