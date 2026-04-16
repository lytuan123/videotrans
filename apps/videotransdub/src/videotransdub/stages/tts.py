from __future__ import annotations

from pathlib import Path

from ..registry import create_tts_engine
from ..utils.srt import read_srt
from ..utils.voice_over import build_voice_over_segments
from .base import BaseStage


class TTSStage(BaseStage):
    name = "stage3_tts"

    def run(self, ctx):
        stage_dir = ctx.workspace.stage_dir("stage3")
        input_key = "voice_over_script_srt" if ctx.settings.voice_over.enabled and ctx.artifacts.get("voice_over_script_srt") else "transcript_translated_srt"
        input_srt = Path(ctx.artifacts[input_key])
        if ctx.settings.voice_over.enabled:
            if not ctx.voice_over_segments:
                if input_key == "voice_over_script_srt":
                    ctx.voice_over_segments = read_srt(input_srt)
                else:
                    translated_segments = read_srt(input_srt)
                    ctx.voice_over_segments = build_voice_over_segments(
                        translated_segments,
                        max_chunk_chars=ctx.settings.voice_over.max_chunk_chars,
                        max_gap_seconds=ctx.settings.voice_over.max_gap_seconds,
                        min_chunk_seconds=ctx.settings.voice_over.min_chunk_seconds,
                    )
            source_segments = ctx.voice_over_segments
        else:
            if not ctx.translated_segments:
                ctx.translated_segments = read_srt(input_srt)
            source_segments = ctx.translated_segments
        engine = create_tts_engine(ctx.settings, ctx.log_path)
        outputs = engine.synthesize(source_segments, input_srt, stage_dir)
        return {f"tts_{key}": value for key, value in outputs.items()}
