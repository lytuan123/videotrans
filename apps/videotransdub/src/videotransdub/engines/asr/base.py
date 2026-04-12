from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ...models import SubtitleSegment


class BaseASREngine(ABC):
    @abstractmethod
    def transcribe(self, input_path: Path, output_dir: Path) -> list[SubtitleSegment]:
        raise NotImplementedError
