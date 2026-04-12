from __future__ import annotations

from pathlib import Path

from ..registry import create_tts_engine
from ..utils.srt import read_srt
from .base import BaseStage


class TTSStage(BaseStage):
    name = "stage3_tts"

    def run(self, ctx):
        stage_dir = ctx.workspace.stage_dir("stage3")
        input_srt = Path(ctx.artifacts["transcript_translated_srt"])
        if not ctx.translated_segments:
            ctx.translated_segments = read_srt(input_srt)
        engine = create_tts_engine(ctx.settings, ctx.log_path)
        outputs = engine.synthesize(ctx.translated_segments, input_srt, stage_dir)
        return {f"tts_{key}": value for key, value in outputs.items()}
