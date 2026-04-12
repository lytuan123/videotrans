from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseInpaintEngine(ABC):
    @abstractmethod
    def clean(self, video_path: Path, output_path: Path) -> Path:
        raise NotImplementedError
