from __future__ import annotations

import shutil
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from videotransdub.diagnostics import build_pipeline_overrides, collect_preflight, run_smoke, run_voice_preview
from videotransdub.settings import load_settings


class DiagnosticsTests(unittest.TestCase):
    def test_build_pipeline_overrides_returns_none_when_empty(self) -> None:
        self.assertIsNone(build_pipeline_overrides(None, None, None))

    def test_preflight_mock_mode_can_be_ready_without_execute_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "sample.mp4"
            video.write_text("fake video", encoding="utf-8")
            config = tmp_path / "config.yaml"
            config.write_text(
                f"""
runtime:
  mode: mock
pipeline:
  video_path: {video}
  target_language: vi
asr:
  engine: mock
translation:
  engine: mock
tts:
  engine: mock
""",
                encoding="utf-8",
            )
            report = collect_preflight(load_settings(str(config)))
            self.assertTrue(report["ready"])
            self.assertTrue(report["checks"]["input_video"]["ok"])

    def test_preflight_reports_missing_qwen_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "sample.mp4"
            video.write_text("fake video", encoding="utf-8")
            config = tmp_path / "config.yaml"
            config.write_text(
                f"""
pipeline:
  video_path: {video}
  target_language: vi
asr:
  engine: qwen3-asr
  model: qwen3-asr-flash
  qwen_api_key: ""
translation:
  engine: qwen-mt
  qwen_api_key: ""
tts:
  engine: mock
""",
                encoding="utf-8",
            )
            report = collect_preflight(load_settings(str(config)))
            self.assertFalse(report["ready"])
            self.assertFalse(report["checks"]["env:QWEN_API_KEY:asr"]["ok"])
            self.assertFalse(report["checks"]["env:QWEN_API_KEY:translate"]["ok"])

    def test_smoke_mock_mode_can_fallback_without_ffmpeg(self) -> None:
        tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(tmp_path, ignore_errors=True))
        video = tmp_path / "sample.mp4"
        video.write_text("fake video", encoding="utf-8")
        config = tmp_path / "config.yaml"
        config.write_text(
            f"""
runtime:
  mode: mock
pipeline:
  video_path: {video}
  target_language: vi
asr:
  engine: mock
translation:
  engine: mock
tts:
  engine: mock
video_processing:
  burn_subtitle: false
""",
            encoding="utf-8",
        )
        settings = load_settings(str(config))
        with mock.patch("videotransdub.diagnostics.which", return_value=None):
            report = run_smoke(settings, clip_seconds=5, work_root=str(tmp_path / "smoke"))
        self.assertEqual(report["clip_mode"], "copy-input-video")
        self.assertTrue(Path(report["final_video"]).exists())

    def test_voice_preview_mock_mode_outputs_audio_only_artifacts(self) -> None:
        tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(tmp_path, ignore_errors=True))
        video = tmp_path / "sample.mp4"
        video.write_text("fake video", encoding="utf-8")
        config = tmp_path / "config.yaml"
        config.write_text(
            f"""
runtime:
  mode: mock
pipeline:
  video_path: {video}
  target_language: vi
voice_over:
  enabled: true
asr:
  engine: mock
translation:
  engine: mock
tts:
  engine: mock
video_processing:
  burn_subtitle: false
""",
            encoding="utf-8",
        )
        settings = load_settings(str(config))
        with mock.patch("videotransdub.diagnostics.which", return_value=None):
            report = run_voice_preview(settings, clip_seconds=5, work_root=str(tmp_path / "preview"))
        self.assertEqual(report["clip_mode"], "copy-input-video")
        self.assertTrue(Path(report["voice_over_script_srt"]).exists())
        self.assertTrue(Path(report["narration_audio"]).exists())
        self.assertTrue(Path(report["mixed_audio"]).exists())


if __name__ == "__main__":
    unittest.main()
