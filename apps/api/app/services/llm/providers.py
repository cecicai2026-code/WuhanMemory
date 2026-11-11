from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import Settings
from app.services.llm.base import LLMJsonResult


class MockLLMProvider:
    name = "mock"

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        temperature: float,
        trace_id: str,
    ) -> LLMJsonResult:
        return LLMJsonResult(
            provider=self.name,
            model="mock-wuhan-planner-v1",
            payload={
                "city": "武汉",
                "intent": "plan_itinerary",
                "traceId": trace_id,
                "message": user_prompt,
            },
            raw={"systemPrompt": system_prompt, "schema": schema, "temperature": temperature},
        )


class OpenAICompatibleProvider:
    def __init__(self, *, name: str, api_key: str | None, base_url: str, model: str | None) -> None:
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        temperature: float,
        trace_id: str,
    ) -> LLMJsonResult:
        if not self.api_key or not self.model:
            raise RuntimeError(f"{self.name} provider is not configured")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                    "x-wuhanmemory-trace-id": trace_id,
                },
                json=payload,
            )
            response.raise_for_status()
            raw = response.json()

        content = raw["choices"][0]["message"]["content"]
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError:
            parsed_content = {"rawJsonText": content}

        return LLMJsonResult(
            provider=self.name,
            model=self.model,
            payload=parsed_content,
            raw=raw,
        )


def build_provider(name: str, settings: Settings):
    if name == "mock":
        return MockLLMProvider()
    if name == "qwen":
        return OpenAICompatibleProvider(
            name="qwen",
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            model=settings.qwen_model,
        )
    if name == "doubao":
        return OpenAICompatibleProvider(
            name="doubao",
            api_key=settings.doubao_api_key,
            base_url=settings.doubao_base_url,
            model=settings.doubao_model,
        )
    raise ValueError(f"Unsupported LLM provider: {name}")
