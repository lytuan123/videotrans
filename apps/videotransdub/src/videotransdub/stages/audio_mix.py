from __future__ import annotations

from pathlib import Path

from ..utils.commands import write_json
from .base import BaseStage


class AudioMixStage(BaseStage):
    name = "stage4_mix"

    def run(self, ctx):
        stage_dir = ctx.workspace.stage_dir("stage4")
        mix_manifest = stage_dir / "mixed_audio.json"
        source = ctx.artifacts.get("synced_audio") or ctx.artifacts.get("tts_audio", "")
        write_json(mix_manifest, {
            "source": source,
            "bgm_strategy": "passthrough-disabled" if not ctx.settings.vocal_separation.enabled else ctx.settings.vocal_separation.engine,
            "normalize": ctx.settings.audio_mix.normalize,
            "target_lufs": ctx.settings.audio_mix.target_lufs,
        })
        return {"mixed_audio_manifest": str(mix_manifest), "mixed_audio": source}
