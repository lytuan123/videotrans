from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

from videotransdub.orchestrator import VideoTransDubOrchestrator
from videotransdub.settings import load_settings


class PipelineTests(unittest.TestCase):
    def test_mock_pipeline_creates_final_manifest(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
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
  workspace_dir: {tmp_path / 'workspace'}
  output_dir: {tmp_path / 'output'}
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
            orchestrator = VideoTransDubOrchestrator(settings)
            manifest = orchestrator.run()
            final_video = Path(manifest.artifacts["final_video"])
            self.assertTrue(final_video.exists())
            self.assertEqual(final_video.read_text(encoding="utf-8"), "fake video")
            checkpoint = Path(manifest.workspace_root) / "manifests" / "checkpoint.json"
            self.assertTrue(checkpoint.exists())


if __name__ == "__main__":
    unittest.main()
