from __future__ import annotations

from pathlib import Path

from ..utils.commands import write_json
from .base import BaseStage


class AudioSyncStage(BaseStage):
    name = "stage3_5_sync"

    def run(self, ctx):
        stage_dir = ctx.workspace.stage_dir("stage3_5")
        sync_plan = []
        for segment in ctx.translated_segments:
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
