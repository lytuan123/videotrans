from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
import unittest

from videotransdub.models import SubtitleSegment
from videotransdub.orchestrator import VideoTransDubOrchestrator
from videotransdub.settings import load_settings
from videotransdub.utils.voice_over import build_voice_over_segments


class VoiceOverTests(unittest.TestCase):
    def test_build_voice_over_segments_merges_close_lines(self) -> None:
        segments = [
            SubtitleSegment(id=0, start=0.0, end=1.2, text="Hello", translated_text="Xin chao"),
            SubtitleSegment(id=1, start=1.4, end=2.1, text="world", translated_text="the gioi"),
            SubtitleSegment(id=2, start=5.0, end=6.0, text="again", translated_text="lan nua"),
        ]
        chunks = build_voice_over_segments(
            segments,
            max_chunk_chars=40,
            max_gap_seconds=1.0,
            min_chunk_seconds=2.0,
        )
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].text, "Xin chao. the gioi")
        self.assertEqual(chunks[0].metadata["source_segment_ids"], [0, 1])

    def test_mock_voice_over_pipeline_emits_script_and_mixed_audio(self) -> None:
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
  workspace_dir: {tmp_path / 'workspace'}
  output_dir: {tmp_path / 'output'}
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
        orchestrator = VideoTransDubOrchestrator(settings)
        manifest = orchestrator.run()
        self.assertIn("voice_over_script_srt", manifest.artifacts)
        self.assertTrue(Path(manifest.artifacts["voice_over_script_srt"]).exists())
        self.assertIn("mixed_audio", manifest.artifacts)
        self.assertTrue(Path(manifest.artifacts["mixed_audio"]).exists())


if __name__ == "__main__":
    unittest.main()
