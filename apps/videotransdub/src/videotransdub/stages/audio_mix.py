from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..utils.commands import run_command, which, write_json
from .base import BaseStage


class AudioMixStage(BaseStage):
    name = "stage4_mix"

    def run(self, ctx):
        stage_dir = ctx.workspace.stage_dir("stage4")
        mix_manifest = stage_dir / "mixed_audio.json"
        source = ctx.artifacts.get("synced_audio") or ctx.artifacts.get("tts_audio", "")
        payload = {
            "source": source,
            "bgm_strategy": "passthrough-disabled" if not ctx.settings.vocal_separation.enabled else ctx.settings.vocal_separation.engine,
            "normalize": ctx.settings.audio_mix.normalize,
            "target_lufs": ctx.settings.audio_mix.target_lufs,
        }

        if ctx.settings.voice_over.enabled and source:
            mixed_audio = stage_dir / f"voice_over_mix.{ctx.settings.output.audio_codec}"
            payload["mode"] = "voice_over"
            payload["voice_over_source"] = source
            mixed_result = self._mix_voice_over(ctx, Path(source), mixed_audio)
            payload.update(mixed_result["payload"])
            write_json(mix_manifest, payload)
            return {
                "mixed_audio_manifest": str(mix_manifest),
                "mixed_audio": mixed_result["audio"],
            }

        write_json(mix_manifest, payload)
        return {"mixed_audio_manifest": str(mix_manifest), "mixed_audio": source}

    def _mix_voice_over(self, ctx, narration_audio: Path, mixed_audio: Path) -> dict[str, object]:
        ffmpeg = which(ctx.settings.runtime.ffmpeg_bin)
        source_video = Path(ctx.artifacts["source_video"])
        payload: dict[str, object] = {
            "voice_over_enabled": True,
            "narration_audio": str(narration_audio),
            "ducking": ctx.settings.voice_over.ducking,
        }

        if not narration_audio.exists():
            raise FileNotFoundError(f"Voice-over narration audio not found: {narration_audio}")

        if not ffmpeg or ctx.settings.runtime.mode != "execute":
            payload["mix_mode"] = "passthrough-narration"
            return {"audio": str(narration_audio), "payload": payload}

        if not self._source_video_has_audio(ctx):
            run_command(
                [
                    ctx.settings.runtime.ffmpeg_bin,
                    "-y",
                    "-i",
                    str(narration_audio),
                    "-c:a",
                    ctx.settings.output.audio_codec,
                    "-b:a",
                    ctx.settings.output.audio_bitrate,
                    str(mixed_audio),
                ],
                cwd=None,
                log_path=ctx.log_path,
            )
            payload["mix_mode"] = "narration-only-encode"
            return {"audio": str(mixed_audio), "payload": payload}

        filter_complex = self._build_voice_over_filter(ctx)
        try:
            run_command(
                [
                    ctx.settings.runtime.ffmpeg_bin,
                    "-y",
                    "-i",
                    str(source_video),
                    "-i",
                    str(narration_audio),
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[mix]",
                    "-c:a",
                    ctx.settings.output.audio_codec,
                    "-b:a",
                    ctx.settings.output.audio_bitrate,
                    str(mixed_audio),
                ],
                cwd=None,
                log_path=ctx.log_path,
            )
            payload["mix_mode"] = "ffmpeg-voice-over-duck"
            payload["filter_complex"] = filter_complex
            return {"audio": str(mixed_audio), "payload": payload}
        except Exception:
            shutil.copy2(narration_audio, mixed_audio)
            payload["mix_mode"] = "fallback-copy-narration"
            return {"audio": str(mixed_audio), "payload": payload}

    @staticmethod
    def _build_voice_over_filter(ctx) -> str:
        background_gain = ctx.settings.voice_over.original_audio_gain_db
        narration_gain = ctx.settings.voice_over.narration_gain_db
        if ctx.settings.voice_over.ducking:
            return (
                f"[0:a]aresample=async=1:first_pts=0,volume={background_gain}dB[bg];"
                f"[1:a]aresample=async=1:first_pts=0,volume={narration_gain}dB[narr];"
                "[bg][narr]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[ducked];"
                "[ducked][narr]amix=inputs=2:weights='1 1':normalize=0:duration=longest[mix]"
            )
        return (
            f"[0:a]aresample=async=1:first_pts=0,volume={background_gain}dB[bg];"
            f"[1:a]aresample=async=1:first_pts=0,volume={narration_gain}dB[narr];"
            "[bg][narr]amix=inputs=2:weights='1 1':normalize=0:duration=longest[mix]"
        )

    @staticmethod
    def _source_video_has_audio(ctx) -> bool:
        metadata_json = ctx.artifacts.get("metadata_json")
        if not metadata_json:
            return True
        metadata_path = Path(metadata_json)
        if not metadata_path.exists():
            return True
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return True
        streams = payload.get("ffprobe", {}).get("streams", [])
        if not streams:
            return True
        return any(stream.get("codec_type") == "audio" for stream in streams)
