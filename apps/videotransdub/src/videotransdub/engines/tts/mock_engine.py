from __future__ import annotations

from pathlib import Path

from ...models import SubtitleSegment
from ...settings import AppSettings
from ...utils.commands import write_json
from .base import BaseTTSEngine


class MockTTSEngine(BaseTTSEngine):
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def synthesize(self, segments: list[SubtitleSegment], input_srt: Path, output_dir: Path) -> dict[str, str]:
        manifest = output_dir / "dubbed_segments.json"
        audio = output_dir / "dubbed_full.mock.wav"
        payload = {
            "engine": "mock",
            "voice": self.settings.tts.mock_voice_label,
            "segments": [
                {
                    "id": segment.id,
                    "text": segment.translated_text or segment.text,
                    "start": segment.start,
                    "end": segment.end,
                }
                for segment in segments
            ],
        }
        write_json(manifest, payload)
        audio.write_text("mock audio placeholder", encoding="utf-8")
        return {"manifest": str(manifest), "audio": str(audio)}
