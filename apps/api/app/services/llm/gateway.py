from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.services.llm.base import LLMJsonResult
from app.services.llm.providers import build_provider


class LLMGateway:
    def __init__(self) -> None:
        self.primary = build_provider(settings.llm_provider, settings)
        self.fallback = (
            build_provider(settings.llm_fallback_provider, settings)
            if settings.llm_fallback_provider
            else None
        )
        self.mode = settings.llm_provider_mode

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        temperature: float = 0.2,
    ) -> LLMJsonResult:
        trace_id = str(uuid4())
        try:
            return await self.primary.complete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
                temperature=temperature,
                trace_id=trace_id,
            )
        except Exception:
            if self.mode == "fallback" and self.fallback is not None:
                return await self.fallback.complete_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    schema=schema,
                    temperature=temperature,
                    trace_id=trace_id,
                )
            raise


llm_gateway = LLMGateway()
