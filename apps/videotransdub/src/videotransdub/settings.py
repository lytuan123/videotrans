from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _read_colab_secret(key: str) -> str | None:
    try:
        from google.colab import userdata  # type: ignore
    except Exception:
        return None

    try:
        value = userdata.get(key)
    except Exception:
        return None
    return value or None


def _lookup_env(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    if value:
        return value
    secret = _read_colab_secret(key)
    if secret:
        return secret
    return default


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            default = match.group(2) or ""
            return _lookup_env(key, default)
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
    upstream_repo_root: str = Field(default_factory=lambda: str(_repo_root()))
    upstream_cli_path: str = Field(default_factory=lambda: str(_repo_root() / "cli.py"))
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    python_bin: str = "python"
    keep_stage_outputs: bool = True

    @model_validator(mode="after")
    def normalize_paths(self) -> "RuntimeSettings":
        repo_root = Path(self.upstream_repo_root).expanduser()
        if not repo_root.is_absolute():
            repo_root = (_repo_root() / repo_root).resolve()
        else:
            repo_root = repo_root.resolve()

        cli_path = Path(self.upstream_cli_path).expanduser()
        if not cli_path.is_absolute():
            cli_path = (repo_root / cli_path).resolve()
        else:
            cli_path = cli_path.resolve()

        self.upstream_repo_root = str(repo_root)
        self.upstream_cli_path = str(cli_path)
        return self


class PipelineSettings(BaseModel):
    video_path: str | None = None
    output_dir: str = "./runtime/output"
    workspace_dir: str = "./runtime/workspace"
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
    qwen_api_key: str = "${QWEN_API_KEY:}"
    qwen_base_url: str = "${QWEN_BASE_URL:}"
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
    qwen_base_url: str = "${QWEN_BASE_URL:}"


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


class VoiceOverSettings(BaseModel):
    enabled: bool = False
    max_chunk_chars: int = 260
    max_gap_seconds: float = 1.2
    min_chunk_seconds: float = 2.0
    ducking: bool = True
    original_audio_gain_db: int = -14
    narration_gain_db: int = 3


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
    voice_over: VoiceOverSettings = Field(default_factory=VoiceOverSettings)
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
