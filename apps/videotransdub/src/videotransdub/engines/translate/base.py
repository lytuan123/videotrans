from __future__ import annotations

from abc import ABC, abstractmethod

from ...models import SubtitleSegment


class BaseTranslator(ABC):
    @abstractmethod
    def translate(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        raise NotImplementedError
