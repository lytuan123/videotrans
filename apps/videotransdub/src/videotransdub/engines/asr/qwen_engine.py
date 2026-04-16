from __future__ import annotations

import logging
import os
from pathlib import Path

from ...models import SubtitleSegment
from ...settings import AppSettings
from ...utils.commands import run_command
from .base import BaseASREngine

logger = logging.getLogger(__name__)


class Qwen3ASREngine(BaseASREngine):
    """Wrap the legacy pyvideotrans Qwen3-ASR path behind the new stage pipeline."""

    def __init__(self, settings: AppSettings, workspace_log: Path) -> None:
        self.settings = settings
        self.workspace_log = workspace_log
        self.base_url = (
            settings.asr.qwen_base_url
            or os.environ.get("QWEN_BASE_URL")
            or os.environ.get("DASHSCOPE_BASE_URL")
            or "https://dashscope.aliyuncs.com/api/v1"
        )

    def transcribe(self, input_path: Path, output_dir: Path) -> list[SubtitleSegment]:
        wav_path = output_dir / "input_16k.wav"
        self._extract_audio(input_path, wav_path)
        rows = self._transcribe_with_legacy_qwen(wav_path, output_dir)

        segments: list[SubtitleSegment] = []
        for row in rows:
            text = str(row.get("text", "")).strip()
            if not text:
                continue
            segments.append(
                SubtitleSegment(
                    id=len(segments),
                    start=float(row["start_time"]) / 1000.0,
                    end=float(row["end_time"]) / 1000.0,
                    text=text,
                    metadata={
                        "engine": "qwen3-asr",
                        "model": self.settings.asr.model,
                    },
                )
            )

        if not segments:
            raise RuntimeError("Qwen3-ASR returned no subtitle segments")
        return segments

    def _extract_audio(self, input_path: Path, wav_path: Path) -> None:
        output_dir = wav_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        run_command(
            [
                self.settings.runtime.ffmpeg_bin,
                "-y",
                "-i",
                str(input_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                str(wav_path),
            ],
            cwd=None,
            log_path=self.workspace_log,
        )

    def _transcribe_with_legacy_qwen(self, wav_path: Path, output_dir: Path) -> list[dict]:
        try:
            import dashscope
            from videotrans.configure import config as legacy_config
            from videotrans.recognition._qwen3asr import Qwen3ASRRecogn
        except ImportError as exc:
            raise RuntimeError(
                "Legacy pyvideotrans Qwen3-ASR integration is unavailable in this checkout."
            ) from exc

        api_key = self.settings.asr.qwen_api_key
        if not api_key:
            raise ValueError(
                "Qwen API key is required for qwen3-asr. "
                "Set asr.qwen_api_key in config or QWEN_API_KEY in the environment."
            )

        dashscope.base_http_api_url = self.base_url
        legacy_config.init_run()
        legacy_config.params["qwenmt_key"] = api_key
        legacy_config.params["qwenmt_asr_model"] = self.settings.asr.model

        language = self.settings.pipeline.source_language
        if not language or language == "auto":
            language = "auto"

        logger.info("Qwen3-ASR via legacy adapter: model=%s, base_url=%s", self.settings.asr.model, self.base_url)
        recognizer = Qwen3ASRRecogn(
            detect_language=language,
            audio_file=str(wav_path),
            cache_folder=str(output_dir),
            model_name=self.settings.asr.model,
            is_cuda=self.settings.asr.cuda,
            recogn_type=7,
        )
        result = recognizer.run()
        return result or []
