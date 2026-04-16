from __future__ import annotations

from pathlib import Path

from ..utils.srt import read_srt
from ..utils.commands import write_json
from .base import BaseStage


class AudioSyncStage(BaseStage):
    name = "stage3_5_sync"

    def run(self, ctx):
        stage_dir = ctx.workspace.stage_dir("stage3_5")
        sync_plan = []
        if ctx.settings.voice_over.enabled:
            if not ctx.voice_over_segments and ctx.artifacts.get("voice_over_script_srt"):
                ctx.voice_over_segments = read_srt(Path(ctx.artifacts["voice_over_script_srt"]))
            source_segments = ctx.voice_over_segments
        else:
            source_segments = ctx.translated_segments

        for segment in source_segments:
            ratio = 1.0
            sync_plan.append({
                "segment_id": segment.id,
                "start": segment.start,
                "end": segment.end,
                "target_duration": segment.duration,
                "stretch_ratio": ratio,
            })
        sync_plan_path = stage_dir / "sync_plan.json"
        write_json(sync_plan_path, {
            "method": ctx.settings.audio_sync.method,
            "segments": sync_plan,
            "limits": {
                "max_speedup": ctx.settings.audio_sync.max_speedup,
                "max_slowdown": ctx.settings.audio_sync.max_slowdown,
            },
        })
        audio_source = ctx.artifacts.get("tts_audio") or ctx.artifacts.get("tts_manifest", "")
        return {"sync_plan": str(sync_plan_path), "synced_audio": audio_source}
