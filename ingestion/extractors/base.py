"""
Abstract base extractor.
Every file type extractor must inherit from this.
Adding a new file type = add one new class, nothing else changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionResult:
    """
    Structured result from any extractor.
    Consistent shape regardless of file type.
    """
    text: str
    page_count: int = 0
    word_count: int = 0
    extraction_method: str = "unknown"
    warnings: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.word_count = len(self.text.split()) if self.text else 0

    @property
    def is_empty(self) -> bool:
        return not self.text or not self.text.strip()

    @property
    def char_count(self) -> int:
        return len(self.text) if self.text else 0


class BaseExtractor(ABC):
    """
    Abstract base for all file extractors.
    Subclasses implement _extract() — base handles logging and error wrapping.
    """

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return list of supported file extensions e.g. ['pdf']"""
        pass

    @abstractmethod
    def _extract(self, filepath: str) -> ExtractionResult:
        """
        Core extraction logic.
        Implement this in each subclass.
        """
        pass

    def extract(self, filepath: str) -> ExtractionResult:
        """
        Public extraction method with logging and error handling.
        Never call _extract() directly — always call this.
        """
        import os
        filename = os.path.basename(filepath)

        self.logger.info(
            "extraction_started",
            filename=filename,
            extractor=self.__class__.__name__
        )

        result = self._extract(filepath)

        self.logger.info(
            "extraction_completed",
            filename=filename,
            extractor=self.__class__.__name__,
            pages=result.page_count,
            words=result.word_count,
            method=result.extraction_method,
            warnings=len(result.warnings)
        )

        return result

    def can_handle(self, filepath: str) -> bool:
        """Check if this extractor handles the given file."""
        ext = filepath.rsplit(".", 1)[-1].lower()
        return ext in self.supported_extensions