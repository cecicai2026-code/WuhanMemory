"""按 .env 的设置建网关。业务代码和接口都通过 get_llm_gateway() 拿网关。"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, settings
from app.repositories.llm_call_repository import SqliteLLMCallRepository
from app.services.llm.gateway import LLMGateway, Recorder
from app.services.llm.providers import build_providers


def build_gateway(config: Settings, *, recorder: Recorder | None = None) -> LLMGateway:
    return LLMGateway(
        providers=build_providers(config),
        default_provider=config.llm_provider,
        # 自动换备用模型默认关着：悄悄换模型会让"这次用了哪个模型"说不清
        fallback_provider=config.llm_fallback_provider if config.llm_provider_mode == "fallback" else None,
        timeout_seconds=config.llm_request_timeout_seconds,
        max_retries=config.llm_max_retries,
        recorder=recorder,
    )


@lru_cache
def get_llm_gateway() -> LLMGateway:
    calls = SqliteLLMCallRepository(settings.database_path)
    return build_gateway(settings, recorder=calls.add)
