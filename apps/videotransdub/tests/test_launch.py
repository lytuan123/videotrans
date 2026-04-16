from __future__ import annotations

import unittest

from videotransdub.launch import app_path, build_streamlit_command


class LaunchTests(unittest.TestCase):
    def test_build_streamlit_command_uses_package_app_path(self) -> None:
        command = build_streamlit_command(9999)
        self.assertEqual(command[:3], ["streamlit", "run", str(app_path())])
        self.assertIn("9999", command)


if __name__ == "__main__":
    unittest.main()
