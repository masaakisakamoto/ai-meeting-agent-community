from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterable, Dict, Optional


@dataclass
class LLMRequest:
    prompt: str
    system: str = ""
    model: str = ""
    temperature: float = 0.0
    response_format: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    text: str
    model: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    id: str
    name: str

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    async def stream(self, request: LLMRequest) -> AsyncIterable[str]:
        yield self.generate(request).text
