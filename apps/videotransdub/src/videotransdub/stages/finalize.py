from __future__ import annotations

import shutil
from pathlib import Path

from ..utils.commands import run_command, which, write_json
from .base import BaseStage


def build_finalize_command(
    ffmpeg_bin: str,
    video_input: Path,
    mixed_audio: Path,
    final_video: Path,
    *,
    video_codec: str,
    audio_codec: str,
    audio_bitrate: str,
) -> list[str]:
    return [
        ffmpeg_bin,
        "-y",
        "-i", str(video_input),
        "-i", str(mixed_audio),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", video_codec,
        "-c:a", audio_codec,
        "-b:a", audio_bitrate,
        "-shortest",
        str(final_video),
    ]


class FinalizeStage(BaseStage):
    name = "stage6_finalize"

    def run(self, ctx):
        output_dir = ctx.workspace.stage_dir("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        final_video = output_dir / f"final.{ctx.settings.output.format}"
        video_input = Path(ctx.artifacts["video_subbed"])
        mixed_audio = ctx.artifacts.get("mixed_audio")
        manifest_path = output_dir / "final_manifest.json"
        payload = {
            "video_input": str(video_input),
            "mixed_audio": mixed_audio,
            "video_codec": ctx.settings.output.video_codec,
            "audio_codec": ctx.settings.output.audio_codec,
        }
        ffmpeg = which(ctx.settings.runtime.ffmpeg_bin)
        if ffmpeg and ctx.settings.runtime.mode == "execute" and mixed_audio and Path(mixed_audio).exists() and video_input.exists() and video_input.suffix != ".txt":
            run_command(
                build_finalize_command(
                    ctx.settings.runtime.ffmpeg_bin,
                    video_input,
                    Path(mixed_audio),
                    final_video,
                    video_codec=ctx.settings.output.video_codec,
                    audio_codec=ctx.settings.output.audio_codec,
                    audio_bitrate=ctx.settings.output.audio_bitrate,
                ),
                cwd=None,
                log_path=ctx.log_path,
            )
            payload["finalize_mode"] = "ffmpeg-mux"
        else:
            if video_input.exists():
                shutil.copy2(video_input, final_video)
            else:
                final_video.write_text("final placeholder", encoding="utf-8")
            payload["finalize_mode"] = "copy-or-placeholder"
        write_json(manifest_path, payload)
        return {"final_video": str(final_video), "final_manifest": str(manifest_path)}
