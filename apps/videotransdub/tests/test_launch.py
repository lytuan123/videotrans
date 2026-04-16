from __future__ import annotations

import os
import unittest

from videotransdub.launch import app_path, app_root, build_streamlit_command, build_streamlit_env


class LaunchTests(unittest.TestCase):
    def test_build_streamlit_command_uses_package_app_path(self) -> None:
        command = build_streamlit_command(9999)
        self.assertEqual(command[:3], ["streamlit", "run", str(app_path())])
        self.assertIn("9999", command)

    def test_build_streamlit_env_prepends_src_to_pythonpath(self) -> None:
        env = build_streamlit_env({"PYTHONPATH": "existing_path"})
        self.assertEqual(
            env["PYTHONPATH"],
            os.pathsep.join([str(app_root() / "src"), "existing_path"]),
        )


if __name__ == "__main__":
    unittest.main()
