from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from ...models import SubtitleSegment
from ...settings import AppSettings
from ...utils.commands import write_json
from .base import BaseTTSEngine

logger = logging.getLogger(__name__)


class EdgeTTSEngine(BaseTTSEngine):
    """Real TTS engine using Microsoft Edge-TTS (free, no API key)."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def synthesize(
        self,
        segments: list[SubtitleSegment],
        input_srt: Path,
        output_dir: Path,
    ) -> dict[str, str]:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "edge-tts is not installed. Run: pip install edge-tts"
            ) from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        voice = self.settings.tts.voice_role
        rate = self.settings.tts.voice_rate
        volume = self.settings.tts.volume
        pitch = self.settings.tts.pitch

        logger.info("Edge-TTS: voice=%s, %d segments", voice, len(segments))

        segment_manifest: list[dict] = []

        loop = asyncio.new_event_loop()
        try:
            for seg in segments:
                text = seg.translated_text or seg.text
                if not text.strip():
                    continue

                audio_file = output_dir / f"seg_{seg.id:04d}.mp3"
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=voice,
                    rate=rate,
                    volume=volume,
                    pitch=pitch,
                )
                loop.run_until_complete(communicate.save(str(audio_file)))

                segment_manifest.append({
                    "id": seg.id,
                    "text": text,
                    "start": seg.start,
                    "end": seg.end,
                    "audio_file": str(audio_file),
                })
                logger.info("  TTS seg %d -> %s", seg.id, audio_file.name)
        finally:
            loop.close()

        manifest_path = output_dir / "dubbed_segments.json"
        write_json(manifest_path, {
            "engine": "edge-tts",
            "voice": voice,
            "segments": segment_manifest,
        })

        concat_audio = self._concat_segments(output_dir, segment_manifest, segments)

        return {
            "manifest": str(manifest_path),
            "audio": str(concat_audio),
        }

    def _concat_segments(
        self,
        output_dir: Path,
        manifest_entries: list[dict],
        segments: list[SubtitleSegment],
    ) -> Path:
        """Concatenate per-segment audio into a single dubbed track with silence padding."""
        from ...utils.commands import run_command, which

        concat_path = output_dir / "dubbed_full.mp3"

        if not manifest_entries:
            concat_path.write_bytes(b"")
            return concat_path

        ffmpeg = which("ffmpeg")
        if not ffmpeg:
            first = manifest_entries[0].get("audio_file", "")
            if first and Path(first).exists():
                import shutil
                shutil.copy2(first, concat_path)
            return concat_path

        filter_parts: list[str] = []
        input_args: list[str] = []
        n_inputs = 0

        for entry in manifest_entries:
            audio_file = entry["audio_file"]
            if not Path(audio_file).exists():
                continue
            input_args.extend(["-i", audio_file])
            start_ms = int(entry["start"] * 1000)
            filter_parts.append(
                f"[{n_inputs}]adelay={start_ms}|{start_ms}[d{n_inputs}]"
            )
            n_inputs += 1

        if n_inputs == 0:
            concat_path.write_bytes(b"")
            return concat_path

        mix_inputs = "".join(f"[d{i}]" for i in range(n_inputs))
        filter_complex = ";".join(filter_parts) + f";{mix_inputs}amix=inputs={n_inputs}:normalize=0[out]"

        cmd = [
            ffmpeg, "-y",
            *input_args,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-ac", "1",
            str(concat_path),
        ]
        try:
            run_command(cmd, cwd=None)
        except Exception as exc:
            logger.warning("Failed to concat audio: %s", exc)
            first = manifest_entries[0].get("audio_file", "")
            if first and Path(first).exists():
                import shutil
                shutil.copy2(first, concat_path)

        return concat_path
