from __future__ import annotations

from pathlib import Path

from ..registry import create_translate_engine
from ..utils.commands import write_json
from ..utils.srt import read_srt, write_srt
from ..utils.voice_over import build_voice_over_segments
from .base import BaseStage


class TranslateStage(BaseStage):
    name = "stage2_translate"

    def run(self, ctx):
        stage_dir = ctx.workspace.stage_dir("stage2")
        input_srt = Path(ctx.artifacts["transcript_raw_srt"])
        if not ctx.segments:
            ctx.segments = read_srt(input_srt)
        engine = create_translate_engine(ctx.settings, ctx.log_path, input_srt)
        translated = engine.translate(ctx.segments)
        if ctx.settings.translation.engine == "pyvideotrans-sts" and ctx.settings.runtime.mode != "mock":
            for idx, segment in enumerate(translated):
                original = ctx.segments[idx] if idx < len(ctx.segments) else segment
                translated[idx] = original.model_copy(update={"translated_text": segment.text})
        ctx.translated_segments = translated
        json_path = stage_dir / "transcript_translated.json"
        srt_path = stage_dir / "transcript_translated.srt"
        write_json(json_path, {"segments": [segment.model_dump(mode="json") for segment in translated]})
        write_srt(srt_path, translated, translated=True)
        outputs = {
            "transcript_translated_json": str(json_path),
            "transcript_translated_srt": str(srt_path),
        }

        if ctx.settings.voice_over.enabled:
            ctx.voice_over_segments = build_voice_over_segments(
                translated,
                max_chunk_chars=ctx.settings.voice_over.max_chunk_chars,
                max_gap_seconds=ctx.settings.voice_over.max_gap_seconds,
                min_chunk_seconds=ctx.settings.voice_over.min_chunk_seconds,
            )
            voice_json_path = stage_dir / "voice_over_script.json"
            voice_srt_path = stage_dir / "voice_over_script.srt"
            write_json(voice_json_path, {"segments": [segment.model_dump(mode="json") for segment in ctx.voice_over_segments]})
            write_srt(voice_srt_path, ctx.voice_over_segments)
            outputs["voice_over_script_json"] = str(voice_json_path)
            outputs["voice_over_script_srt"] = str(voice_srt_path)

        return outputs
