"""
Abstract LLM interface.
The rest of the app never imports Ollama directly — only this interface.
Swap LLM providers by adding a new class, nothing else changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LLMResponse:
    """Normalized response from any LLM."""
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    generation_time_ms: float = 0.0

    @property
    def is_empty(self) -> bool:
        return not self.content or not self.content.strip()


class BaseLLM(ABC):
    """
    Abstract base for all LLM implementations.
    Implement this to add any new LLM provider.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1
    ) -> LLMResponse:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass