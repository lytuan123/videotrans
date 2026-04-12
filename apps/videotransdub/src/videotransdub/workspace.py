from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .settings import AppSettings


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\-.]+", "-", value.strip())
    value = re.sub(r"-+", "-", value)
    return value.strip("-") or "job"


class Workspace:
    def __init__(self, root: Path, job_id: str) -> None:
        self.root = root / job_id
        self.job_id = job_id
        self.stage_dirs = {
            "stage0": self.root / "stage0",
            "stage1": self.root / "stage1",
            "stage2": self.root / "stage2",
            "stage3": self.root / "stage3",
            "stage3_5": self.root / "stage3_5",
            "stage4": self.root / "stage4",
            "stage5": self.root / "stage5",
            "output": self.root / "output",
            "logs": self.root / "logs",
            "manifests": self.root / "manifests",
        }

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "Workspace":
        video_path = settings.pipeline.video_path or settings.pipeline.job_name or "video"
        stem = Path(video_path).stem or "video"
        digest = hashlib.sha1(str(Path(video_path)).encode("utf-8")).hexdigest()[:8]
        job_name = settings.pipeline.job_name or slugify(stem)
        return cls(Path(settings.pipeline.workspace_dir).expanduser().resolve(), f"{job_name}-{digest}")

    def prepare(self) -> None:
        for directory in self.stage_dirs.values():
            directory.mkdir(parents=True, exist_ok=True)

    def stage_dir(self, stage: str) -> Path:
        return self.stage_dirs[stage]

    def artifact_path(self, stage: str, name: str, suffix: str) -> Path:
        return self.stage_dir(stage) / f"{name}{suffix}"

    @property
    def log_file(self) -> Path:
        return self.stage_dirs["logs"] / "pipeline.log"

    @property
    def manifest_file(self) -> Path:
        return self.stage_dirs["manifests"] / "job.json"

    @property
    def checkpoint_file(self) -> Path:
        return self.stage_dirs["manifests"] / "checkpoint.json"
