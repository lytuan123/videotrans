from __future__ import annotations

from pathlib import Path

from ...models import SubtitleSegment
from ...settings import AppSettings
from ...utils.commands import run_command, snapshot_files
from ...utils.srt import read_srt
from .base import BaseTranslator


class PyVideoTransTranslator(BaseTranslator):
    def __init__(self, settings: AppSettings, workspace_log: Path, input_srt: Path) -> None:
        self.settings = settings
        self.workspace_log = workspace_log
        self.input_srt = input_srt

    def translate(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        repo_root = Path(self.settings.runtime.upstream_repo_root).resolve()
        output_root = repo_root / "output"
        before = snapshot_files(output_root, [".srt"])
        command = self._build_command(self.input_srt)
        run_command(command, cwd=repo_root, log_path=self.workspace_log)
        after = snapshot_files(output_root, [".srt"])
        created = sorted(after - before, key=lambda item: item.stat().st_mtime, reverse=True)
        target = created[0] if created else self._latest_srt(output_root)
        if target is None:
            raise FileNotFoundError("pyvideotrans STS did not produce an SRT output")
        return read_srt(target)

    def _build_command(self, input_srt: Path) -> list[str]:
        cli_path = self.settings.runtime.upstream_cli_path
        if self.settings.runtime.prefer_uv:
            command = ["uv", "run", cli_path]
        else:
            command = [self.settings.runtime.python_bin, cli_path]
        command += [
            "--task", "sts",
            "--name", str(input_srt),
            "--translate_type", str(self.settings.translation.translate_type),
            "--source_language_code", self.settings.pipeline.source_language,
            "--target_language_code", self.settings.pipeline.target_language,
        ]
        return command

    @staticmethod
    def _latest_srt(output_root: Path) -> Path | None:
        candidates = sorted(output_root.rglob("*.srt"), key=lambda item: item.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None
