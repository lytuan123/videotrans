from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SubtitleWord(BaseModel):
    word: str
    start: float
    end: float


class SubtitleSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    translated_text: str | None = None
    audio_path: str | None = None
    words: list[SubtitleWord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class StageResult(BaseModel):
    stage: str
    status: str
    started_at: str = Field(default_factory=utc_now)
    completed_at: str | None = None
    outputs: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class JobManifest(BaseModel):
    job_id: str
    config_path: str | None = None
    source_video: str
    workspace_root: str
    artifacts: dict[str, str] = Field(default_factory=dict)
    stages: dict[str, StageResult] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)

    def dump_json(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
