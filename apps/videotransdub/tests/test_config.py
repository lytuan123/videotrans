from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
from unittest import mock

import videotransdub.settings as settings_module
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

    def test_qwen_key_can_fallback_to_colab_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yaml"
            config.write_text(
                "pipeline:\n  target_language: vi\ntranslation:\n  qwen_api_key: ${QWEN_API_KEY:}\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch.object(settings_module, "_read_colab_secret", return_value="colab-secret"):
                    settings = load_settings(str(config))
            self.assertEqual(settings.translation.qwen_api_key, "colab-secret")

    def test_runtime_defaults_resolve_upstream_cli_to_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yaml"
            config.write_text("pipeline:\n  target_language: vi\n", encoding="utf-8")
            settings = load_settings(str(config))
            self.assertTrue(Path(settings.runtime.upstream_repo_root).is_absolute())
            self.assertTrue(Path(settings.runtime.upstream_cli_path).is_absolute())
            self.assertTrue(Path(settings.runtime.upstream_cli_path).exists())


if __name__ == "__main__":
    unittest.main()
