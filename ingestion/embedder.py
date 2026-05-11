"""
Embedding model wrapper for Nexus.
Singleton pattern — model loaded once, reused forever.
Loading a sentence-transformer model takes 3-5 seconds.
We never want to load it more than once.
"""

from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from core.config import get_settings
from core.exceptions import EmbeddingFailedError
from core.logger import get_logger, TimedOperation

logger = get_logger(__name__)
settings = get_settings()


class EmbeddingModel:
    """
    Singleton embedding model wrapper.
    Thread-safe lazy initialization.
    """

    _instance: Optional["EmbeddingModel"] = None
    _model: Optional[SentenceTransformer] = None

    def __new__(cls) -> "EmbeddingModel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self) -> None:
        """
        Load the embedding model into memory.
        Call once at application startup.
        Takes 3-10 seconds depending on hardware.
        """
        if self._model is not None:
            logger.debug("embedding_model_already_loaded")
            return

        try:
            logger.info(
                "embedding_model_loading",
                model=settings.EMBEDDING_MODEL
            )

            with TimedOperation(logger, "embedding_model_load"):
                self._model = SentenceTransformer(
                    settings.EMBEDDING_MODEL,
                    device="cpu"  # Force CPU — no GPU on this machine
                )

            # Warm up with a dummy encode
            self._model.encode(["warmup"], batch_size=1)

            logger.info(
                "embedding_model_loaded",
                model=settings.EMBEDDING_MODEL,
                dimension=self.dimension
            )

        except Exception as e:
            logger.error(
                "embedding_model_load_failed",
                model=settings.EMBEDDING_MODEL,
                error=str(e)
            )
            raise EmbeddingFailedError(f"Model load failed: {str(e)}")

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self.load()
        return self._model

    @property
    def dimension(self) -> int:
        """Vector dimension of the current model."""
        return self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string.
        Returns normalized float list ready for Qdrant.
        """
        if not text or not text.strip():
            raise EmbeddingFailedError("Cannot embed empty text")

        try:
            with TimedOperation(logger, "single_embedding"):
                vector = self.model.encode(
                    text,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
            return vector.tolist()

        except Exception as e:
            raise EmbeddingFailedError(f"Embedding failed: {str(e)}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of texts.
        Much faster than embedding one by one.
        """
        if not texts:
            return []

        # Filter out empty strings
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            raise EmbeddingFailedError("All texts in batch are empty")

        try:
            with TimedOperation(
                logger,
                "batch_embedding",
                batch_size=len(valid_texts)
            ):
                vectors = self.model.encode(
                    valid_texts,
                    batch_size=settings.EMBEDDING_BATCH_SIZE,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )

            return [v.tolist() for v in vectors]

        except Exception as e:
            raise EmbeddingFailedError(f"Batch embedding failed: {str(e)}")


# Module level singleton
embedding_model = EmbeddingModel()