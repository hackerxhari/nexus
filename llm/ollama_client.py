"""
Ollama LLM client for Nexus.
Implements BaseLLM using local Ollama server.
Handles retries, timeouts, and graceful degradation.
"""

import time
from typing import Optional

import ollama
from ollama import ResponseError

from core.config import get_settings
from core.exceptions import (
    GenerationFailedError,
    GenerationTimeoutError,
    ModelNotAvailableError
)
from core.logger import get_logger, TimedOperation
from llm.base import BaseLLM, LLMResponse
from llm.prompt_builder import PromptBuilder

logger = get_logger(__name__)
settings = get_settings()


class OllamaClient(BaseLLM):
    """
    Ollama LLM implementation.
    Connects to locally running Ollama server.
    """

    def __init__(self, model: Optional[str] = None):
        self._model = model or settings.OLLAMA_MODEL
        self._client = ollama.Client(
            host=settings.OLLAMA_HOST,
            timeout=settings.OLLAMA_TIMEOUT
        )

    @property
    def model_name(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Check if Ollama server and model are reachable."""
        try:
            models = self._client.list()
            available = [m.model for m in models.models]
            return any(self._model in m for m in available)
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1
    ) -> LLMResponse:
        """
        Generate a response from Ollama.
        Retries on transient failures.
        Raises specific exceptions on permanent failures.
        """
        if not prompt or not prompt.strip():
            raise GenerationFailedError("Prompt cannot be empty")

        system = system_prompt or PromptBuilder.BASE_SYSTEM_PROMPT
        last_error = None

        for attempt in range(1, settings.OLLAMA_MAX_RETRIES + 1):
            try:
                with TimedOperation(
                    logger,
                    "ollama_generate",
                    model=self._model,
                    attempt=attempt
                ) as op:
                    start = time.perf_counter()

                    response = self._client.chat(
                        model=self._model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt}
                        ],
                        options={
                            "temperature": settings.OLLAMA_TEMPERATURE,
                            "num_predict": settings.OLLAMA_NUM_PREDICT,
                            "num_ctx": settings.OLLAMA_NUM_CTX,
                            "top_p": settings.OLLAMA_TOP_P,
                            "top_k": settings.OLLAMA_TOP_K,
                            "repeat_penalty": settings.OLLAMA_REPEAT_PENALTY
                        }
                    )

                    generation_time_ms = (
                        time.perf_counter() - start
                    ) * 1000

                content = response.message.content

                if not content or not content.strip():
                    raise GenerationFailedError(
                        "Model returned empty response"
                    )

                logger.info(
                    "ollama_generation_success",
                    model=self._model,
                    generation_time_ms=round(generation_time_ms, 2),
                    response_length=len(content),
                    attempt=attempt
                )

                return LLMResponse(
                    content=content.strip(),
                    model=self._model,
                    generation_time_ms=round(generation_time_ms, 2)
                )

            except GenerationFailedError:
                raise

            except ResponseError as e:
                if "model" in str(e).lower() and "not found" in str(e).lower():
                    raise ModelNotAvailableError(self._model)
                last_error = e
                logger.warning(
                    "ollama_attempt_failed",
                    attempt=attempt,
                    max_retries=settings.OLLAMA_MAX_RETRIES,
                    error=str(e)
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    "ollama_attempt_failed",
                    attempt=attempt,
                    max_retries=settings.OLLAMA_MAX_RETRIES,
                    error=str(e)
                )

                if attempt < settings.OLLAMA_MAX_RETRIES:
                    # Exponential backoff: 1s, 2s, 4s
                    wait = 2 ** (attempt - 1)
                    logger.debug("ollama_retry_wait", seconds=wait)
                    time.sleep(wait)

        raise GenerationFailedError(
            f"Failed after {settings.OLLAMA_MAX_RETRIES} attempts: {str(last_error)}"
        )

    def prewarm(self, prompt: Optional[str] = None) -> None:
        """Load the model into memory to avoid first-request latency."""
        warm_prompt = (prompt or settings.OLLAMA_PREWARM_PROMPT).strip()
        if not warm_prompt:
            warm_prompt = "hi"

        try:
            self._client.chat(
                model=self._model,
                messages=[{"role": "user", "content": warm_prompt}],
                options={"num_predict": 1}
            )
            logger.info("ollama_prewarm_success", model=self._model)
        except Exception as e:
            logger.warning(
                "ollama_prewarm_failed",
                model=self._model,
                error=str(e)
            )


# Module level singleton
ollama_client = OllamaClient()