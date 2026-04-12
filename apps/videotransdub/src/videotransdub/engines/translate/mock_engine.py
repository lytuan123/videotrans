from __future__ import annotations

from ...models import SubtitleSegment
from ...settings import AppSettings
from .base import BaseTranslator


class MockTranslator(BaseTranslator):
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def translate(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        prefix = self.settings.translation.mock_prefix
        translated: list[SubtitleSegment] = []
        for segment in segments:
            translated.append(segment.model_copy(update={"translated_text": f"{prefix}{segment.text}"}))
        return translated
