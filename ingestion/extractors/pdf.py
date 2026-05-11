"""
PDF extractor with fallback to OCR for scanned pages.
Strategy:
  1. Try pdfplumber (fast, accurate for digital PDFs)
  2. If page has no text → OCR that page via pytesseract
  3. Track which pages needed OCR for debugging
"""

import os
from typing import List

import pdfplumber
import pytesseract
from PIL import Image

from core.exceptions import ExtractionFailedError
from core.logger import get_logger
from ingestion.extractors.base import BaseExtractor, ExtractionResult

logger = get_logger(__name__)

# Minimum characters per page to consider it "has text"
MIN_CHARS_PER_PAGE = 20


class PDFExtractor(BaseExtractor):

    @property
    def supported_extensions(self) -> List[str]:
        return ["pdf"]

    def _extract(self, filepath: str) -> ExtractionResult:
        if not os.path.exists(filepath):
            raise ExtractionFailedError(
                os.path.basename(filepath),
                "File not found"
            )

        full_text = []
        page_count = 0
        ocr_pages = []
        warnings = []

        try:
            with pdfplumber.open(filepath) as pdf:
                page_count = len(pdf.pages)

                if page_count == 0:
                    raise ExtractionFailedError(
                        os.path.basename(filepath),
                        "PDF has no pages"
                    )

                for page_num, page in enumerate(pdf.pages, start=1):
                    try:
                        page_text = page.extract_text() or ""

                        if len(page_text.strip()) >= MIN_CHARS_PER_PAGE:
                            # Digital page — use extracted text
                            full_text.append(page_text)
                        else:
                            # Scanned page — fall back to OCR
                            logger.debug(
                                "pdf_page_ocr_fallback",
                                page=page_num,
                                filename=os.path.basename(filepath)
                            )
                            ocr_text = self._ocr_page(page)
                            if ocr_text.strip():
                                full_text.append(ocr_text)
                                ocr_pages.append(page_num)
                            else:
                                warnings.append(
                                    f"Page {page_num}: no text extracted"
                                )

                    except Exception as e:
                        warnings.append(f"Page {page_num} failed: {str(e)}")
                        logger.warning(
                            "pdf_page_extraction_failed",
                            page=page_num,
                            error=str(e)
                        )
                        continue

        except ExtractionFailedError:
            raise
        except Exception as e:
            raise ExtractionFailedError(
                os.path.basename(filepath),
                f"PDF parsing failed: {str(e)}"
            )

        combined_text = "\n\n".join(full_text)

        if ocr_pages:
            warnings.append(f"OCR used on pages: {ocr_pages}")

        method = "mixed" if ocr_pages else "digital"
        if len(ocr_pages) == page_count:
            method = "ocr_only"

        return ExtractionResult(
            text=combined_text,
            page_count=page_count,
            extraction_method=method,
            warnings=warnings,
            metadata={
                "ocr_pages": ocr_pages,
                "total_pages": page_count
            }
        )

    def _ocr_page(self, page) -> str:
        """Convert a PDF page to image and run OCR."""
        try:
            # Render at 300 DPI for good OCR accuracy
            pil_image = page.to_image(resolution=300).original
            text = pytesseract.image_to_string(
                pil_image,
                config="--psm 3"  # Fully automatic page segmentation
            )
            return text
        except Exception as e:
            logger.warning("pdf_ocr_failed", error=str(e))
            return ""