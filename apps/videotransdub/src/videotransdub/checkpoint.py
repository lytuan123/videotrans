from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import utc_now


class CheckpointManager:
    def __init__(self, path: Path) -> None:
        self.path = path
        if path.exists():
            self.state = json.loads(path.read_text(encoding="utf-8"))
        else:
            self.state = {"stages": {}}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8")

    def stage(self, name: str) -> dict[str, Any]:
        return self.state.setdefault("stages", {}).setdefault(name, {})

    def is_completed(self, name: str) -> bool:
        return self.stage(name).get("status") == "completed"

    def mark_running(self, name: str) -> None:
        entry = self.stage(name)
        entry["status"] = "running"
        entry["started_at"] = utc_now()
        self.save()

    def mark_completed(self, name: str, outputs: dict[str, str] | None = None, metrics: dict[str, Any] | None = None) -> None:
        entry = self.stage(name)
        entry["status"] = "completed"
        entry["completed_at"] = utc_now()
        if outputs:
            entry["outputs"] = outputs
        if metrics:
            entry["metrics"] = metrics
        self.save()

    def mark_failed(self, name: str, error: str) -> None:
        entry = self.stage(name)
        entry["status"] = "failed"
        entry["completed_at"] = utc_now()
        entry["error"] = error
        self.save()
