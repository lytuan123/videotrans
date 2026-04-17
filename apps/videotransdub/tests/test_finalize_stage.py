from __future__ import annotations

from pathlib import Path
import unittest

from videotransdub.stages.finalize import build_finalize_command


class FinalizeStageTests(unittest.TestCase):
    def test_finalize_command_prefers_mixed_audio_stream(self) -> None:
        command = build_finalize_command(
            "ffmpeg",
            Path("video.mp4"),
            Path("mix.aac"),
            Path("final.mp4"),
            video_codec="copy",
            audio_codec="aac",
            audio_bitrate="192k",
        )
        self.assertIn("-map", command)
        self.assertEqual(command[command.index("-map") + 1], "0:v:0")
        second_map_index = command.index("-map", command.index("-map") + 1)
        self.assertEqual(command[second_map_index + 1], "1:a:0")
        self.assertIn("-shortest", command)


if __name__ == "__main__":
    unittest.main()
