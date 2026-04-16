from __future__ import annotations

from pathlib import Path
import unittest

from videotransdub.stages.video import _escape_subtitles_filter_path


class VideoStageTests(unittest.TestCase):
    def test_escape_subtitles_filter_path_handles_windows_drive_letter(self) -> None:
        path = Path(r"C:\repo\apps\videotransdub\runtime\workspace\job\stage2\transcript_translated.srt")
        escaped = _escape_subtitles_filter_path(path)
        self.assertIn(r"C\:/repo/apps/videotransdub/runtime/workspace/job/stage2/transcript_translated.srt", escaped)
        self.assertNotIn(r"C:/repo/apps/videotransdub/runtime/workspace/job/stage2/transcript_translated.srt", escaped)


if __name__ == "__main__":
    unittest.main()
