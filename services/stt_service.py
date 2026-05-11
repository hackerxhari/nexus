"""
Lightweight Speech‑to‑Text service using Vosk.
Provides a singleton `stt_service` compatible with existing route code
and a stand‑alone `transcribe_file(file_path)` helper as requested.
"""

import io
import json
import os
import wave
from typing import List, Optional

from vosk import Model, KaldiRecognizer

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)


class VoskSTTService:
    """Singleton‑style service wrapping a Vosk Model.

    Attributes
    ----------
    model_path: str
        Filesystem path to the Vosk model directory.
    model: Model | None
        Loaded Vosk model instance.
    _available: bool
        Whether the model was successfully loaded.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        settings = get_settings()
        self.model_path = model_path or settings.VOSK_MODEL_PATH
        self.model = None
        self._available = False
        self._load_model()

    def _is_model_dir(self, path: str) -> bool:
        return (
            os.path.isfile(os.path.join(path, "conf", "model.conf"))
            or os.path.isfile(os.path.join(path, "am", "final.mdl"))
        )

    def _resolve_model_dir(self, path: str) -> Optional[str]:
        if not path:
            return None
        if os.path.isdir(path) and self._is_model_dir(path):
            return path
        if not os.path.isdir(path):
            return None

        try:
            candidates = [
                os.path.join(path, name)
                for name in sorted(os.listdir(path))
                if os.path.isdir(os.path.join(path, name))
            ]
        except OSError:
            return None

        for candidate in candidates:
            if self._is_model_dir(candidate):
                return candidate
        return None

    def _load_model(self) -> None:
        """Load the Vosk model; set ``_available`` flag.

        The function checks that ``model_path`` exists before attempting to
        instantiate ``Model``. Any failure is logged and the service remains
        unavailable.
        """
        model_dir = self._resolve_model_dir(self.model_path)
        if not model_dir:
            for fallback in ("models", "model"):
                if fallback == self.model_path:
                    continue
                model_dir = self._resolve_model_dir(fallback)
                if model_dir:
                    break

        if not model_dir:
            logger.warning(
                "vosk_model_missing",
                path=self.model_path,
            )
            self._available = False
            return
        try:
            self.model_path = model_dir
            self.model = Model(self.model_path)
            self._available = True
            logger.info(
                "vosk_model_loaded",
                path=self.model_path,
            )
        except Exception as e:
            logger.error(
                "vosk_model_load_failed",
                error=str(e),
            )
            self._available = False

    @property
    def is_available(self) -> bool:
        """Public flag indicating whether transcription can be performed."""
        return self._available and self.model is not None

    def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe raw WAV/PCM bytes to text.

        The audio is expected to be 16 kHz mono as required by KaldiRecognizer.
        If the format differs, a warning is emitted but the recognizer still
        attempts to process the stream.
        """
        if not self.is_available:
            logger.warning("vosk_transcribe_unavailable")
            return ""
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                sample_rate = wf.getframerate()
                if sample_rate != 16000 or wf.getnchannels() != 1:
                    logger.warning(
                        "vosk_invalid_audio_format",
                        expected="16kHz mono",
                        actual=f"{sample_rate}Hz {wf.getnchannels()}ch",
                    )
                rec = KaldiRecognizer(self.model, sample_rate)
                results: List[str] = []
                while True:
                    data = wf.readframes(4000)
                    if not data:
                        break
                    if rec.AcceptWaveform(data):
                        part = json.loads(rec.Result())
                        results.append(part.get("text", ""))
                final = json.loads(rec.FinalResult())
                results.append(final.get("text", ""))
                return " ".join(results).strip()
        except Exception as e:
            logger.error("vosk_transcribe_failed", error=str(e))
            return ""

    def create_recognizer(self, sample_rate: int) -> Optional[KaldiRecognizer]:
        """Create a recognizer for streaming audio at the given sample rate."""
        if not self.is_available:
            logger.warning("vosk_recognizer_unavailable")
            return None
        try:
            rec = KaldiRecognizer(self.model, sample_rate)
            rec.SetWords(True)
            return rec
        except Exception as e:
            logger.error("vosk_recognizer_failed", error=str(e))
            return None


def transcribe_file(file_path: str) -> str:
    """Convenient helper that transcribes a WAV file located at ``file_path``.

    The function mirrors the sample code supplied by the user, ensuring the
    model directory exists before attempting transcription.
    """
    model_dir = "model"
    if not os.path.isdir(model_dir):
        logger.warning("vosk_model_missing", path=model_dir)
        return ""
    try:
        model = Model(model_dir)
        wf = wave.open(file_path, "rb")
        rec = KaldiRecognizer(model, wf.getframerate())
        results: List[str] = []
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if rec.AcceptWaveform(data):
                part = json.loads(rec.Result())
                results.append(part.get("text", ""))
        final = json.loads(rec.FinalResult())
        results.append(final.get("text", ""))
        return " ".join(results).strip()
    except Exception as e:
        logger.error("vosk_file_transcribe_failed", error=str(e))
        return ""


# Module‑level singleton used by API routes
stt_service = VoskSTTService()
