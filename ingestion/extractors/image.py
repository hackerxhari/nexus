"""
Image extractor using OCR.
Handles PNG, JPG, JPEG, TIFF.
Preprocesses image for better OCR accuracy.
"""

import os
from typing import List

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

from core.exceptions import ExtractionFailedError
from core.logger import get_logger
from ingestion.extractors.base import BaseExtractor, ExtractionResult

logger = get_logger(__name__)


class ImageExtractor(BaseExtractor):

    @property
    def supported_extensions(self) -> List[str]:
        return ["png", "jpg", "jpeg", "tiff", "tif", "bmp"]

    def _extract(self, filepath: str) -> ExtractionResult:
        if not os.path.exists(filepath):
            raise ExtractionFailedError(
                os.path.basename(filepath),
                "File not found"
            )

        try:
            image = Image.open(filepath)

            # Preprocess for better OCR
            processed = self._preprocess(image)

            # Run OCR
            text = pytesseract.image_to_string(
                processed,
                config="--psm 3 --oem 3"
            )

            warnings = []
            if len(text.strip()) < 20:
                warnings.append("Very little text extracted — image may be unclear")

            return ExtractionResult(
                text=text,
                page_count=1,
                extraction_method="ocr",
                warnings=warnings,
                metadata={
                    "image_size": image.size,
                    "image_mode": image.mode
                }
            )

        except ExtractionFailedError:
            raise
        except Exception as e:
            raise ExtractionFailedError(
                os.path.basename(filepath),
                f"Image OCR failed: {str(e)}"
            )

    def _preprocess(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for better OCR accuracy.
        Convert to grayscale, enhance contrast, sharpen.
        """
        try:
            # Convert to RGB first if needed
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")

            # Convert to grayscale
            image = image.convert("L")

            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)

            # Sharpen
            image = image.filter(ImageFilter.SHARPEN)

            # Scale up small images for better OCR
            width, height = image.size
            if width < 1000:
                scale = 1000 / width
                new_size = (int(width * scale), int(height * scale))
                image = image.resize(new_size, Image.LANCZOS)

            return image

        except Exception as e:
            logger.warning("image_preprocess_failed", error=str(e))
            return image  # Return original if preprocessing fails