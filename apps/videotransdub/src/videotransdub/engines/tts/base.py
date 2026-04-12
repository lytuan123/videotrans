from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ...models import SubtitleSegment


class BaseTTSEngine(ABC):
    @abstractmethod
    def synthesize(self, segments: list[SubtitleSegment], input_srt: Path, output_dir: Path) -> dict[str, str]:
        raise NotImplementedError
