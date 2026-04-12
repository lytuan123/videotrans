from __future__ import annotations

from pathlib import Path

from ..registry import create_asr_engine
from ..utils.commands import write_json
from ..utils.srt import write_srt
from .base import BaseStage


class ASRStage(BaseStage):
    name = "stage1_asr"

    def run(self, ctx):
        stage_dir = ctx.workspace.stage_dir("stage1")
        source_video = Path(ctx.artifacts["source_video"])
        engine = create_asr_engine(ctx.settings, ctx.log_path)
        segments = engine.transcribe(source_video, stage_dir)
        ctx.segments = segments

        json_path = stage_dir / "transcript_raw.json"
        srt_path = stage_dir / "transcript_raw.srt"
        write_json(json_path, {"segments": [segment.model_dump(mode="json") for segment in segments]})
        write_srt(srt_path, segments)
        return {"transcript_raw_json": str(json_path), "transcript_raw_srt": str(srt_path)}
