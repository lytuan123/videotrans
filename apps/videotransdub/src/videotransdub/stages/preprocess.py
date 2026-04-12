from __future__ import annotations

import json
import os
from pathlib import Path

from ..utils.commands import run_command, which, write_json
from .base import BaseStage


class PreprocessStage(BaseStage):
    name = "stage0_preprocess"

    def run(self, ctx):
        input_path = Path(ctx.settings.pipeline.video_path or "").expanduser().resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")
        stage_dir = ctx.workspace.stage_dir("stage0")
        source_marker = stage_dir / "source_video.txt"
        source_marker.write_text(str(input_path), encoding="utf-8")

        metadata_path = stage_dir / "metadata.json"
        metadata = {
            "input_path": str(input_path),
            "size_bytes": input_path.stat().st_size,
            "source_language": ctx.settings.pipeline.source_language,
            "target_language": ctx.settings.pipeline.target_language,
        }
        ffprobe = which(ctx.settings.runtime.ffprobe_bin)
        if ffprobe and ctx.settings.runtime.mode == "execute":
            try:
                result = run_command([
                    ctx.settings.runtime.ffprobe_bin,
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    str(input_path),
                ], cwd=None, log_path=ctx.log_path)
                metadata["ffprobe"] = json.loads(result.stdout or "{}")
            except Exception as exc:
                metadata["ffprobe_error"] = str(exc)
        write_json(metadata_path, metadata)
        return {
            "source_video": str(input_path),
            "metadata_json": str(metadata_path),
            "source_marker": str(source_marker),
        }
