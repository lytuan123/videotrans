from __future__ import annotations

import importlib.util
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .orchestrator import VideoTransDubOrchestrator
from .settings import AppSettings, deep_merge
from .utils.commands import CommandError, run_command, which


def module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def build_pipeline_overrides(video_path: str | None, target_language: str | None, source_language: str | None) -> dict[str, Any] | None:
    overrides: dict[str, Any] = {"pipeline": {}}
    if video_path:
        overrides["pipeline"]["video_path"] = video_path
    if target_language:
        overrides["pipeline"]["target_language"] = target_language
    if source_language:
        overrides["pipeline"]["source_language"] = source_language
    return overrides if overrides["pipeline"] else None


def collect_preflight(settings: AppSettings, *, check_ui: bool = False) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    warnings: list[str] = []

    def record_check(
        name: str,
        ok: bool,
        *,
        required: bool = True,
        detail_ok: str = "",
        detail_fail: str = "",
    ) -> None:
        detail = detail_ok if ok else detail_fail
        checks[name] = {
            "ok": ok,
            "required": required,
            "detail": detail,
        }
        if required and not ok and detail:
            errors.append(detail)
        elif not required and not ok and detail:
            warnings.append(detail)

    input_video = settings.pipeline.video_path
    if input_video:
        video_path = Path(input_video).expanduser().resolve()
        record_check(
            "input_video",
            video_path.exists(),
            detail_ok=f"Input video ready: {video_path}",
            detail_fail=f"Input video not found: {video_path}",
        )
    else:
        record_check(
            "input_video",
            False,
            detail_fail="No input video configured. Pass --video-path or set pipeline.video_path.",
        )

    needs_ffmpeg = settings.runtime.mode == "execute"
    record_check(
        "ffmpeg",
        which(settings.runtime.ffmpeg_bin) is not None,
        required=needs_ffmpeg,
        detail_ok=f"Binary '{settings.runtime.ffmpeg_bin}' found.",
        detail_fail=f"Binary '{settings.runtime.ffmpeg_bin}' is required for execute mode.",
    )
    record_check(
        "ffprobe",
        which(settings.runtime.ffprobe_bin) is not None,
        required=needs_ffmpeg,
        detail_ok=f"Binary '{settings.runtime.ffprobe_bin}' found.",
        detail_fail=f"Binary '{settings.runtime.ffprobe_bin}' is required for media probing.",
    )

    if settings.asr.engine == "faster-whisper":
        record_check(
            "module:faster_whisper",
            module_available("faster_whisper"),
            detail_ok="Python module 'faster_whisper' is available.",
            detail_fail="Python module 'faster_whisper' is missing.",
        )
    elif settings.asr.engine == "qwen3-asr":
        record_check(
            "module:dashscope.asr",
            module_available("dashscope"),
            detail_ok="Python module 'dashscope' is available for qwen3-asr.",
            detail_fail="Python module 'dashscope' is missing for qwen3-asr.",
        )
        record_check(
            "env:QWEN_API_KEY:asr",
            bool(settings.asr.qwen_api_key),
            detail_ok="Qwen ASR API key is configured.",
            detail_fail="QWEN_API_KEY (or asr.qwen_api_key) is required for qwen3-asr.",
        )

    if settings.translation.engine == "qwen-mt":
        record_check(
            "module:dashscope.translate",
            module_available("dashscope"),
            detail_ok="Python module 'dashscope' is available for qwen-mt.",
            detail_fail="Python module 'dashscope' is missing for qwen-mt.",
        )
        record_check(
            "env:QWEN_API_KEY:translate",
            bool(settings.translation.qwen_api_key),
            detail_ok="Qwen translation API key is configured.",
            detail_fail="QWEN_API_KEY (or translation.qwen_api_key) is required for qwen-mt.",
        )

    if settings.tts.engine == "edge-tts":
        record_check(
            "module:edge_tts",
            module_available("edge_tts"),
            detail_ok="Python module 'edge_tts' is available.",
            detail_fail="Python module 'edge_tts' is missing.",
        )

    if settings.video_processing.remove_hardcoded_sub and settings.video_processing.inpaint_engine == "opencv":
        record_check(
            "module:cv2",
            module_available("cv2"),
            detail_ok="Python module 'cv2' is available for OpenCV inpaint.",
            detail_fail="Python module 'cv2' is missing for OpenCV inpaint.",
        )

    if check_ui:
        record_check(
            "module:streamlit",
            module_available("streamlit"),
            detail_ok="Python module 'streamlit' is available for the web UI.",
            detail_fail="Python module 'streamlit' is missing for the web UI.",
        )
        record_check(
            "binary:cloudflared",
            which("cloudflared") is not None,
            required=False,
            detail_ok="cloudflared is available.",
            detail_fail="cloudflared is optional; without it Colab may need proxy/local URL access.",
        )

    return {
        "ready": not errors,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "config": {
            "mode": settings.runtime.mode,
            "asr_engine": settings.asr.engine,
            "translation_engine": settings.translation.engine,
            "tts_engine": settings.tts.engine,
            "target_language": settings.pipeline.target_language,
        },
    }


def run_smoke(settings: AppSettings, *, clip_seconds: int = 15, work_root: str | None = None) -> dict[str, Any]:
    input_video = Path(settings.pipeline.video_path or "").expanduser().resolve()
    if not input_video.exists():
        raise FileNotFoundError(f"Input video not found: {input_video}")

    ffmpeg = which(settings.runtime.ffmpeg_bin)
    root = Path(work_root).expanduser().resolve() if work_root else Path(tempfile.mkdtemp(prefix="videotransdub-smoke-"))
    root.mkdir(parents=True, exist_ok=True)
    clip_path = root / f"{input_video.stem}-smoke{input_video.suffix}"
    clip_mode = "ffmpeg-copy"

    if ffmpeg is None:
        if settings.runtime.mode != "mock":
            raise RuntimeError(
                f"Binary '{settings.runtime.ffmpeg_bin}' is required for smoke clipping in execute mode. "
                "Install ffmpeg first."
            )
        shutil.copy2(input_video, clip_path)
        clip_mode = "copy-input-video"
    else:
        clip_commands = [
            [
                settings.runtime.ffmpeg_bin,
                "-y",
                "-ss",
                "0",
                "-t",
                str(clip_seconds),
                "-i",
                str(input_video),
                "-c",
                "copy",
                str(clip_path),
            ],
            [
                settings.runtime.ffmpeg_bin,
                "-y",
                "-ss",
                "0",
                "-t",
                str(clip_seconds),
                "-i",
                str(input_video),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(clip_path),
            ],
        ]
        last_error: Exception | None = None
        for idx, command in enumerate(clip_commands):
            try:
                run_command(command, cwd=None)
                clip_mode = "ffmpeg-copy" if idx == 0 else "ffmpeg-reencode"
                last_error = None
                break
            except CommandError as exc:
                last_error = exc
        if last_error is not None:
            raise RuntimeError(f"Could not create smoke clip: {last_error}") from last_error

    overrides = {
        "pipeline": {
            "video_path": str(clip_path),
            "resume": False,
            "job_name": "smoke",
            "workspace_dir": str(root / "workspace"),
            "output_dir": str(root / "output"),
        }
    }
    payload = settings.model_dump(mode="json")
    smoke_settings = AppSettings.model_validate(deep_merge(payload, overrides))
    orchestrator = VideoTransDubOrchestrator(smoke_settings)
    manifest = orchestrator.run()
    return {
        "clip_path": str(clip_path),
        "clip_seconds": clip_seconds,
        "clip_mode": clip_mode,
        "workspace_root": manifest.workspace_root,
        "final_video": manifest.artifacts.get("final_video"),
        "manifest": manifest.model_dump(mode="json"),
    }
