from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict
from typing import Optional

from meeting_agent.providers.llm.base import LLMProvider, LLMRequest, LLMResponse


class OpenAICompatibleProvider(LLMProvider):
    """Minimal OpenAI-compatible chat completions adapter using stdlib urllib.

    This is intentionally not used in tests. It lets the Community shell call
    OpenAI-compatible endpoints while keeping provider logic replaceable.
    """

    id = "openai_compatible"
    name = "OpenAI-compatible Chat Completions"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: int = 60,
    ) -> None:
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.timeout = timeout

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        payload = {
            "model": request.model or self.model,
            "temperature": request.temperature,
            "messages": [
                {"role": "system", "content": request.system or "You are a helpful assistant."},
                {"role": "user", "content": request.prompt},
            ],
        }
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        choice = body["choices"][0]["message"]["content"]
        return LLMResponse(text=choice, model=body.get("model", request.model or self.model), metadata=body)
