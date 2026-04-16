from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from videotransdub.settings import load_settings


class ConfigTests(unittest.TestCase):
    def test_merge_and_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "base.yaml"
            override = Path(tmp) / "override.yaml"
            base.write_text("pipeline:\n  target_language: vi\nasr:\n  engine: mock\n", encoding="utf-8")
            override.write_text("pipeline:\n  target_language: en\n", encoding="utf-8")
            settings = load_settings(str(base), str(override))
            self.assertEqual(settings.pipeline.target_language, "en")
            self.assertEqual(settings.asr.engine, "mock")

    def test_asr_env_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yaml"
            config.write_text(
                "pipeline:\n  target_language: vi\nasr:\n  qwen_api_key: ${QWEN_API_KEY:test-key}\n",
                encoding="utf-8",
            )
            settings = load_settings(str(config))
            self.assertEqual(settings.asr.qwen_api_key, "test-key")


if __name__ == "__main__":
    unittest.main()
