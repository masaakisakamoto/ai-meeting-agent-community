from __future__ import annotations

from meeting_agent.providers.llm.base import LLMProvider, LLMRequest, LLMResponse


class EchoLLMProvider(LLMProvider):
    """Tiny local provider used for smoke tests and offline demos."""

    id = "echo"
    name = "Echo LLM Provider"

    def generate(self, request: LLMRequest) -> LLMResponse:
        text = request.prompt.strip()
        if len(text) > 500:
            text = text[:500] + "…"
        return LLMResponse(text=text, model="echo")
