from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from videotransdub.registry import create_asr_engine
from videotransdub.settings import load_settings


class RegistryTests(unittest.TestCase):
    def test_qwen_asr_engine_can_be_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yaml"
            config.write_text(
                """
pipeline:
  target_language: vi
asr:
  engine: qwen3-asr
  model: qwen3-asr-flash
  qwen_api_key: test-key
translation:
  engine: mock
tts:
  engine: mock
""",
                encoding="utf-8",
            )
            settings = load_settings(str(config))
            engine = create_asr_engine(settings, Path(tmp) / "workspace.log")
            self.assertEqual(engine.__class__.__name__, "Qwen3ASREngine")


if __name__ == "__main__":
    unittest.main()
