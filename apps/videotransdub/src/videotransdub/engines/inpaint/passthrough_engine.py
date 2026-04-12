from __future__ import annotations

import shutil
from pathlib import Path

from .base import BaseInpaintEngine


class PassthroughInpaintEngine(BaseInpaintEngine):
    def clean(self, video_path: Path, output_path: Path) -> Path:
        if video_path.resolve() == output_path.resolve():
            return output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(video_path, output_path)
        return output_path
