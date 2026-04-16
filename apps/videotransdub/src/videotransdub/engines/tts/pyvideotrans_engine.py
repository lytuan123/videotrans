from __future__ import annotations

from pathlib import Path

from ...models import SubtitleSegment
from ...settings import AppSettings
from ...utils.commands import run_command, snapshot_files
from .base import BaseTTSEngine


class PyVideoTransTTSEngine(BaseTTSEngine):
    def __init__(self, settings: AppSettings, workspace_log: Path) -> None:
        self.settings = settings
        self.workspace_log = workspace_log

    def synthesize(self, segments: list[SubtitleSegment], input_srt: Path, output_dir: Path) -> dict[str, str]:
        repo_root = Path(self.settings.runtime.upstream_repo_root).resolve()
        output_root = repo_root / "output"
        before = snapshot_files(output_root, [".wav", ".mp3", ".m4a"])
        command = self._build_command(input_srt)
        run_command(command, cwd=repo_root, log_path=self.workspace_log)
        after = snapshot_files(output_root, [".wav", ".mp3", ".m4a"])
        created = sorted(after - before, key=lambda item: item.stat().st_mtime, reverse=True)
        target = created[0] if created else self._latest_audio(output_root)
        if target is None:
            raise FileNotFoundError("pyvideotrans TTS did not produce an audio output")
        marker = output_dir / "upstream_audio_source.txt"
        marker.write_text(str(target), encoding="utf-8")
        return {"audio": str(target), "marker": str(marker)}

    def _build_command(self, input_srt: Path) -> list[str]:
        cli_path = self.settings.runtime.upstream_cli_path
        if self.settings.runtime.prefer_uv:
            command = ["uv", "run", self.settings.runtime.python_bin, cli_path]
        else:
            command = [self.settings.runtime.python_bin, cli_path]
        command += [
            "--task", "tts",
            "--name", str(input_srt),
            "--tts_type", str(self.settings.tts.tts_type),
            "--voice_role", self.settings.tts.voice_role,
            "--target_language_code", self.settings.pipeline.target_language,
            "--voice_rate", self.settings.tts.voice_rate,
            "--volume", self.settings.tts.volume,
            "--pitch", self.settings.tts.pitch,
        ]
        if self.settings.tts.voice_autorate:
            command.append("--voice_autorate")
        return command

    @staticmethod
    def _latest_audio(output_root: Path) -> Path | None:
        candidates = sorted(
            [path for path in output_root.rglob("*") if path.suffix.lower() in {".wav", ".mp3", ".m4a"}],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None
