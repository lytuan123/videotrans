from __future__ import annotations

from pathlib import Path

from ..registry import create_translate_engine
from ..utils.commands import write_json
from ..utils.srt import read_srt, write_srt
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
        return {"transcript_translated_json": str(json_path), "transcript_translated_srt": str(srt_path)}
