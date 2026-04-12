from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Iterable


class CommandError(RuntimeError):
    pass


def which(binary: str) -> str | None:
    return shutil.which(binary)


def run_command(command: list[str], cwd: Path | None, log_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("$ " + " ".join(command) + "\n")
            if result.stdout:
                handle.write(result.stdout + "\n")
            if result.stderr:
                handle.write(result.stderr + "\n")
    if result.returncode != 0:
        raise CommandError(f"Command failed ({result.returncode}): {' '.join(command)}\n{result.stderr}")
    return result


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def snapshot_files(root: Path, suffixes: Iterable[str]) -> set[Path]:
    suffixes = tuple(suffixes)
    if not root.exists():
        return set()
    return {path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes}
