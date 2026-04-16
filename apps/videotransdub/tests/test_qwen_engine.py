from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from videotransdub.engines.translate.qwen_engine import QwenTranslator
from videotransdub.settings import load_settings


class _FakeResponse:
    code = ""
    message = ""

    class output:
        class choices:
            message = type("Message", (), {"content": "OK"})()

        choices = [type("Choice", (), {"message": type("Message", (), {"content": "OK"})()})()]


class _FakeGeneration:
    @staticmethod
    def call(**kwargs):
        return _FakeResponse()


class _FakeDashscope:
    base_http_api_url = ""
    Generation = _FakeGeneration


class QwenEngineTests(unittest.TestCase):
    def test_translate_configures_dashscope_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yaml"
            config.write_text(
                """
pipeline:
  target_language: vi
translation:
  engine: qwen-mt
  model: qwen2.5-7b-instruct-1m
  qwen_api_key: test-key
  qwen_base_url: https://dashscope-intl.aliyuncs.com/api/v1
""",
                encoding="utf-8",
            )
            settings = load_settings(str(config))
            engine = QwenTranslator(settings)
            engine.translate([])
            self.assertEqual(engine.base_url, "https://dashscope-intl.aliyuncs.com/api/v1")

    def test_translate_batch_uses_configured_dashscope_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yaml"
            config.write_text(
                """
pipeline:
  target_language: vi
translation:
  engine: qwen-mt
  model: qwen-mt-turbo
  qwen_api_key: test-key
  qwen_base_url: https://dashscope-intl.aliyuncs.com/api/v1
""",
                encoding="utf-8",
            )
            settings = load_settings(str(config))
            engine = QwenTranslator(settings)
            fake_dashscope = _FakeDashscope()
            engine._translate_batch(fake_dashscope, "Hello", "Vietnamese")
            self.assertEqual(fake_dashscope.base_http_api_url, "https://dashscope-intl.aliyuncs.com/api/v1")


if __name__ == "__main__":
    unittest.main()
