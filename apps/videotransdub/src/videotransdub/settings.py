from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]+))?\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            default = match.group(2) or ""
            return os.environ.get(key, default)
        return _ENV_PATTERN.sub(_replace, value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class RuntimeSettings(BaseModel):
    mode: Literal["execute", "mock", "plan"] = "execute"
    prefer_uv: bool = True
    upstream_repo_root: str = "."
    upstream_cli_path: str = "cli.py"
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    python_bin: str = "python3"
    keep_stage_outputs: bool = True


class PipelineSettings(BaseModel):
    video_path: str | None = None
    output_dir: str = "./apps/videotransdub/runtime/output"
    workspace_dir: str = "./apps/videotransdub/runtime/workspace"
    source_language: str = "auto"
    target_language: str = "vi"
    resume: bool = True
    job_name: str | None = None

    @model_validator(mode="after")
    def validate_target_language(self) -> "PipelineSettings":
        if not self.target_language:
            raise ValueError("pipeline.target_language is required")
        return self


class VocalSeparationSettings(BaseModel):
    enabled: bool = False
    engine: str = "disabled"
    model: str = "htdemucs_ft"
    device: str = "cuda"


class ASRSettings(BaseModel):
    engine: str = "pyvideotrans-stt"
    model: str = "large-v3"
    recogn_type: int = 0
    compute_type: str = "float16"
    batch_size: int = 16
    vad_filter: bool = True
    word_timestamps: bool = True
    cuda: bool = True
    mock_text: str = "Hello everyone, welcome to VideoTransDub."


class TranslationSettings(BaseModel):
    engine: str = "pyvideotrans-sts"
    model: str = "gemini-2.5-flash"
    translate_type: int = 5
    batch_size: int = 25
    keep_length: bool = True
    glossary: dict[str, str] = Field(default_factory=dict)
    mock_prefix: str = "[vi] "
    qwen_api_key: str = "${QWEN_API_KEY:}"


class TTSSettings(BaseModel):
    engine: str = "pyvideotrans-tts"
    voice_role: str = "vi-VN-HoaiMyNeural"
    tts_type: int = 0
    voice_rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"
    voice_autorate: bool = True
    mock_voice_label: str = "vi-VN-HoaiMyNeural"


class AudioSyncSettings(BaseModel):
    max_speedup: float = 1.4
    max_slowdown: float = 0.8
    method: str = "manifest"
    silence_trim: bool = True


class AudioMixSettings(BaseModel):
    bgm_volume_adjust_db: int = -3
    normalize: bool = True
    target_lufs: int = -16


class SubtitleStyle(BaseModel):
    font: str = "Arial"
    size: int = 22
    color: str = "white"
    outline: int = 2


class VideoProcessingSettings(BaseModel):
    remove_hardcoded_sub: bool = False
    inpaint_engine: str = "passthrough"
    burn_subtitle: bool = True
    subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle)


class OutputSettings(BaseModel):
    format: str = "mp4"
    video_codec: str = "copy"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"


class AppSettings(BaseModel):
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    vocal_separation: VocalSeparationSettings = Field(default_factory=VocalSeparationSettings)
    asr: ASRSettings = Field(default_factory=ASRSettings)
    translation: TranslationSettings = Field(default_factory=TranslationSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    audio_sync: AudioSyncSettings = Field(default_factory=AudioSyncSettings)
    audio_mix: AudioMixSettings = Field(default_factory=AudioMixSettings)
    video_processing: VideoProcessingSettings = Field(default_factory=VideoProcessingSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)

    def resolve_path(self, value: str) -> Path:
        return Path(value).expanduser().resolve()


def load_settings(*config_paths: str, overrides: dict[str, Any] | None = None) -> AppSettings:
    merged: dict[str, Any] = {}
    for raw_path in config_paths:
        if not raw_path:
            continue
        path = Path(raw_path)
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        merged = deep_merge(merged, _expand_env(data))
    if overrides:
        merged = deep_merge(merged, _expand_env(overrides))
    return AppSettings.model_validate(merged)
