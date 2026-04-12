from __future__ import annotations

from pathlib import Path

from ...models import SubtitleSegment, SubtitleWord
from ...settings import AppSettings
from .base import BaseASREngine


class MockASREngine(BaseASREngine):
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def transcribe(self, input_path: Path, output_dir: Path) -> list[SubtitleSegment]:
        text = self.settings.asr.mock_text.strip()
        return [
            SubtitleSegment(
                id=0,
                start=0.0,
                end=4.0,
                text=text,
                words=[SubtitleWord(word=word, start=0.0, end=0.0) for word in text.split()],
                metadata={"engine": "mock", "input": str(input_path)},
            )
        ]
