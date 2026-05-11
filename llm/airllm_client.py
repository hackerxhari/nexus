"""
Local GGUF model client for Nexus.
Implements BaseLLM using llama-cpp-python for fast CPU inference.
Loads a quantized .gguf model file — light on RAM, fast on CPU.
"""

import os
import time
from typing import Optional

from llama_cpp import Llama

from core.config import get_settings
from core.exceptions import (
    GenerationFailedError,
    ModelNotAvailableError
)
from core.logger import get_logger, TimedOperation
from llm.base import BaseLLM, LLMResponse
from llm.prompt_builder import PromptBuilder

logger = get_logger(__name__)
settings = get_settings()


class AirLLMClient(BaseLLM):
    """
    GGUF model client using llama-cpp-python.
    Loads a quantized model for fast, low-RAM CPU inference.
    """

    _model = None
    _initialized = False

    def __init__(self, model: Optional[str] = None):
        self._model_path = model or settings.AIRLLM_MODEL
        self._max_seq_len = settings.AIRLLM_MAX_SEQ_LEN
        self._max_new_tokens = settings.AIRLLM_MAX_NEW_TOKENS

    def _ensure_loaded(self) -> None:
        """Lazy-load the GGUF model on first use."""
        if AirLLMClient._initialized:
            return

        try:
            logger.info(
                "airllm_model_loading",
                model=self._model_path,
            )

            with TimedOperation(logger, "airllm_model_load"):
                AirLLMClient._model = Llama(
                    model_path=self._model_path,
                    n_ctx=self._max_seq_len,
                    n_threads=os.cpu_count() or 4,
                    n_batch=512,
                    verbose=False,
                )

            AirLLMClient._initialized = True
            logger.info(
                "airllm_model_loaded",
                model=self._model_path
            )

        except Exception as e:
            logger.error(
                "airllm_model_load_failed",
                model=self._model_path,
                error=str(e)
            )
            raise ModelNotAvailableError(
                f"Failed to load GGUF model '{self._model_path}': {e}"
            )

    @property
    def model_name(self) -> str:
        return self._model_path

    def is_available(self) -> bool:
        """Check if the model can be loaded."""
        try:
            self._ensure_loaded()
            return AirLLMClient._model is not None
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1
    ) -> LLMResponse:
        """Generate a response using the local GGUF model."""
        if not prompt or not prompt.strip():
            raise GenerationFailedError("Prompt cannot be empty")

        self._ensure_loaded()

        system = system_prompt or PromptBuilder.BASE_SYSTEM_PROMPT
        last_error = None

        for attempt in range(1, settings.AIRLLM_MAX_RETRIES + 1):
            try:
                with TimedOperation(
                    logger,
                    "airllm_generate",
                    model=self._model_path,
                    attempt=attempt
                ):
                    start = time.perf_counter()

                    messages = [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt}
                    ]

                    response = AirLLMClient._model.create_chat_completion(
                        messages=messages,
                        max_tokens=self._max_new_tokens,
                        temperature=max(temperature, 0.01),
                        top_p=0.9,
                        top_k=40,
                        repeat_penalty=1.1,
                    )

                    content = response["choices"][0]["message"]["content"].strip()
                    usage = response.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)

                    generation_time_ms = (
                        time.perf_counter() - start
                    ) * 1000

                if not content:
                    raise GenerationFailedError(
                        "Model returned empty response"
                    )

                logger.info(
                    "airllm_generation_success",
                    model=self._model_path,
                    generation_time_ms=round(generation_time_ms, 2),
                    response_length=len(content),
                    input_tokens=prompt_tokens,
                    attempt=attempt
                )

                return LLMResponse(
                    content=content,
                    model=self._model_path,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    generation_time_ms=round(generation_time_ms, 2)
                )

            except GenerationFailedError:
                raise

            except Exception as e:
                last_error = e
                logger.warning(
                    "airllm_attempt_failed",
                    attempt=attempt,
                    max_retries=settings.AIRLLM_MAX_RETRIES,
                    error=str(e)
                )

                if attempt < settings.AIRLLM_MAX_RETRIES:
                    wait = 2 ** (attempt - 1)
                    logger.debug("airllm_retry_wait", seconds=wait)
                    time.sleep(wait)

        raise GenerationFailedError(
            f"GGUF model failed after {settings.AIRLLM_MAX_RETRIES} "
            f"attempts: {str(last_error)}"
        )


# Module-level singleton
airllm_client = AirLLMClient()
