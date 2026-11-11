from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMJsonResult:
    provider: str
    model: str
    payload: dict[str, Any]
    raw: dict[str, Any] | None = None


class LLMProvider(Protocol):
    name: str

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        temperature: float,
        trace_id: str,
    ) -> LLMJsonResult:
        ...
