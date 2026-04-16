from __future__ import annotations

import logging
from pathlib import Path

from ...models import SubtitleSegment, SubtitleWord
from ...settings import AppSettings
from .base import BaseASREngine

logger = logging.getLogger(__name__)


class WhisperASREngine(BaseASREngine):
    """Real ASR engine using faster-whisper (CTranslate2 backend)."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper"
            ) from exc

        device = "cuda" if self.settings.asr.cuda else "cpu"
        compute_type = self.settings.asr.compute_type
        if device == "cpu" and compute_type == "float16":
            compute_type = "int8"

        logger.info(
            "Loading Whisper model=%s device=%s compute=%s",
            self.settings.asr.model,
            device,
            compute_type,
        )
        try:
            self._model = WhisperModel(
                self.settings.asr.model,
                device=device,
                compute_type=compute_type,
            )
        except Exception as exc:
            message = str(exc)
            if "LocalEntryNotFoundError" in exc.__class__.__name__ or "cannot find the appropriate snapshot folder" in message:
                raise RuntimeError(
                    f"Whisper model '{self.settings.asr.model}' is not cached locally and could not be downloaded. "
                    "Pre-download the model, restore network access, or switch to a different ASR engine."
                ) from exc
            raise
        return self._model

    def transcribe(self, input_path: Path, output_dir: Path) -> list[SubtitleSegment]:
        model = self._load_model()
        language = self.settings.pipeline.source_language
        if language == "auto":
            language = None

        segments_iter, info = model.transcribe(
            str(input_path),
            language=language,
            beam_size=5,
            vad_filter=self.settings.asr.vad_filter,
            word_timestamps=self.settings.asr.word_timestamps,
        )
        logger.info(
            "Detected language: %s (prob=%.2f), duration=%.1fs",
            info.language,
            info.language_probability,
            info.duration,
        )

        result: list[SubtitleSegment] = []
        for seg in segments_iter:
            words: list[SubtitleWord] = []
            if seg.words:
                for w in seg.words:
                    words.append(SubtitleWord(word=w.word.strip(), start=w.start, end=w.end))

            result.append(
                SubtitleSegment(
                    id=len(result),
                    start=seg.start,
                    end=seg.end,
                    text=seg.text.strip(),
                    words=words,
                    metadata={
                        "engine": "faster-whisper",
                        "model": self.settings.asr.model,
                        "language": info.language,
                        "avg_logprob": getattr(seg, "avg_logprob", None),
                    },
                )
            )

        logger.info("Transcribed %d segments", len(result))
        return result
