from __future__ import annotations

import re
from pathlib import Path

from ...models import SubtitleSegment
from ...settings import AppSettings
from ...utils.commands import run_command, snapshot_files
from ...utils.srt import read_srt
from .base import BaseASREngine


class PyVideoTransASREngine(BaseASREngine):
    def __init__(self, settings: AppSettings, workspace_log: Path) -> None:
        self.settings = settings
        self.workspace_log = workspace_log

    def transcribe(self, input_path: Path, output_dir: Path) -> list[SubtitleSegment]:
        repo_root = Path(self.settings.runtime.upstream_repo_root).resolve()
        output_root = repo_root / "output"
        before = snapshot_files(output_root, [".srt"])
        command = self._build_command(input_path)
        run_command(command, cwd=repo_root, log_path=self.workspace_log)
        after = snapshot_files(output_root, [".srt"])
        created = sorted(after - before, key=lambda item: item.stat().st_mtime, reverse=True)
        target = created[0] if created else self._latest_srt(output_root)
        if target is None:
            raise FileNotFoundError("pyvideotrans STT did not produce an SRT output")
        segments = read_srt(target)
        (output_dir / "upstream_source.txt").write_text(str(target), encoding="utf-8")
        return segments

    def _build_command(self, input_path: Path) -> list[str]:
        cli_path = self.settings.runtime.upstream_cli_path
        if self.settings.runtime.prefer_uv:
            command = ["uv", "run", self.settings.runtime.python_bin, cli_path]
        else:
            command = [self.settings.runtime.python_bin, cli_path]
        command += [
            "--task", "stt",
            "--name", str(input_path),
            "--recogn_type", str(self.settings.asr.recogn_type),
            "--detect_language", self.settings.pipeline.source_language,
            "--model_name", self.settings.asr.model,
        ]
        if self.settings.asr.cuda:
            command.append("--cuda")
        return command

    @staticmethod
    def _latest_srt(output_root: Path) -> Path | None:
        candidates = sorted(output_root.rglob("*.srt"), key=lambda item: item.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None
