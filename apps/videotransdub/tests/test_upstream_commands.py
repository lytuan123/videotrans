from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from videotransdub.engines.asr.pyvideotrans_engine import PyVideoTransASREngine
from videotransdub.engines.translate.pyvideotrans_engine import PyVideoTransTranslator
from videotransdub.engines.tts.pyvideotrans_engine import PyVideoTransTTSEngine
from videotransdub.settings import load_settings


class UpstreamCommandTests(unittest.TestCase):
    def _load_settings(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config = Path(tmp.name) / "config.yaml"
        config.write_text(
            "pipeline:\n  target_language: vi\n",
            encoding="utf-8",
        )
        return load_settings(str(config))

    def test_translate_command_runs_cli_via_python_under_uv(self) -> None:
        settings = self._load_settings()
        engine = PyVideoTransTranslator(settings, Path("workspace.log"), Path("input.srt"))
        command = engine._build_command(Path("input.srt"))
        self.assertEqual(command[:4], ["uv", "run", settings.runtime.python_bin, settings.runtime.upstream_cli_path])

    def test_tts_command_runs_cli_via_python_under_uv(self) -> None:
        settings = self._load_settings()
        engine = PyVideoTransTTSEngine(settings, Path("workspace.log"))
        command = engine._build_command(Path("input.srt"))
        self.assertEqual(command[:4], ["uv", "run", settings.runtime.python_bin, settings.runtime.upstream_cli_path])

    def test_asr_command_runs_cli_via_python_under_uv(self) -> None:
        settings = self._load_settings()
        engine = PyVideoTransASREngine(settings, Path("workspace.log"))
        command = engine._build_command(Path("input.mp4"))
        self.assertEqual(command[:4], ["uv", "run", settings.runtime.python_bin, settings.runtime.upstream_cli_path])


if __name__ == "__main__":
    unittest.main()
