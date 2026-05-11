"""
Plain text extractor.
Handles .txt files with encoding detection.
"""

import os
from typing import List

from core.exceptions import ExtractionFailedError
from core.logger import get_logger
from ingestion.extractors.base import BaseExtractor, ExtractionResult

logger = get_logger(__name__)

# Encodings to try in order
ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "ascii"]


class TXTExtractor(BaseExtractor):

    @property
    def supported_extensions(self) -> List[str]:
        return ["txt", "md", "csv", "log"]

    def _extract(self, filepath: str) -> ExtractionResult:
        if not os.path.exists(filepath):
            raise ExtractionFailedError(
                os.path.basename(filepath),
                "File not found"
            )

        text = None
        used_encoding = None
        warnings = []

        # Try encodings in order until one works
        for encoding in ENCODINGS:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    text = f.read()
                used_encoding = encoding
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if text is None:
            raise ExtractionFailedError(
                os.path.basename(filepath),
                "Could not decode file with any supported encoding"
            )

        if used_encoding != "utf-8":
            warnings.append(f"File decoded using {used_encoding} encoding")

        # Basic cleanup
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        return ExtractionResult(
            text=text,
            page_count=1,
            extraction_method=f"text_reader_{used_encoding}",
            warnings=warnings,
            metadata={"encoding": used_encoding}
        )