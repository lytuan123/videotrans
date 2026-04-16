from __future__ import annotations

from pathlib import Path

from .engines.asr.mock_engine import MockASREngine
from .engines.asr.pyvideotrans_engine import PyVideoTransASREngine
from .engines.inpaint.passthrough_engine import PassthroughInpaintEngine
from .engines.translate.mock_engine import MockTranslator
from .engines.translate.pyvideotrans_engine import PyVideoTransTranslator
from .engines.tts.mock_engine import MockTTSEngine
from .engines.tts.pyvideotrans_engine import PyVideoTransTTSEngine
from .settings import AppSettings


def create_asr_engine(settings: AppSettings, workspace_log: Path):
    if settings.asr.engine == "mock" or settings.runtime.mode == "mock":
        return MockASREngine(settings)
    if settings.asr.engine == "faster-whisper":
        from .engines.asr.whisper_engine import WhisperASREngine
        return WhisperASREngine(settings)
    if settings.asr.engine == "qwen3-asr":
        from .engines.asr.qwen_engine import Qwen3ASREngine
        return Qwen3ASREngine(settings, workspace_log)
    if settings.asr.engine == "pyvideotrans-stt":
        return PyVideoTransASREngine(settings, workspace_log)
    raise ValueError(f"Unsupported ASR engine: {settings.asr.engine}")


def create_translate_engine(settings: AppSettings, workspace_log: Path, input_srt: Path):
    if settings.translation.engine == "mock" or settings.runtime.mode == "mock":
        return MockTranslator(settings)
    if settings.translation.engine == "qwen-mt":
        from .engines.translate.qwen_engine import QwenTranslator
        return QwenTranslator(settings)
    if settings.translation.engine == "pyvideotrans-sts":
        return PyVideoTransTranslator(settings, workspace_log, input_srt)
    raise ValueError(f"Unsupported translation engine: {settings.translation.engine}")


def create_tts_engine(settings: AppSettings, workspace_log: Path):
    if settings.tts.engine == "mock" or settings.runtime.mode == "mock":
        return MockTTSEngine(settings)
    if settings.tts.engine == "edge-tts":
        from .engines.tts.edge_tts_engine import EdgeTTSEngine
        return EdgeTTSEngine(settings)
    if settings.tts.engine == "pyvideotrans-tts":
        return PyVideoTransTTSEngine(settings, workspace_log)
    raise ValueError(f"Unsupported TTS engine: {settings.tts.engine}")


def create_inpaint_engine(settings: AppSettings):
    if settings.video_processing.inpaint_engine == "passthrough" or not settings.video_processing.remove_hardcoded_sub:
        return PassthroughInpaintEngine()
    if settings.video_processing.inpaint_engine == "opencv":
        from .engines.inpaint.opencv_engine import OpenCVInpaintEngine
        return OpenCVInpaintEngine()
    raise ValueError(f"Unsupported inpaint engine: {settings.video_processing.inpaint_engine}")
