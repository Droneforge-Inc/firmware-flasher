import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import build


class BuildTests(unittest.TestCase):
    def test_validate_mode_normalizes_universal(self):
        self.assertEqual(build.validate_mode("universal", system_name="Darwin"), "universal2")

    def test_validate_mode_rejects_universal_off_macos(self):
        with self.assertRaisesRegex(ValueError, "only supported on macOS"):
            build.validate_mode("universal", system_name="Linux")

    def test_venv_python_path_posix(self):
        path = build.venv_python_path(Path("/tmp/example"), os_name="posix")
        self.assertEqual(path, Path("/tmp/example/bin/python"))

    def test_venv_python_path_windows(self):
        path = build.venv_python_path(Path("C:/example"), os_name="nt")
        self.assertEqual(path, Path("C:/example/Scripts/python.exe"))

    def test_artifact_path_windows(self):
        artifact = build.artifact_path(os_name="nt")
        self.assertEqual(artifact.name, "flash-helper.exe")

    def test_artifact_path_posix(self):
        artifact = build.artifact_path(os_name="posix")
        self.assertEqual(artifact.name, "flash-helper")

    def test_build_pythonpath_prepends_root(self):
        with mock.patch.dict(os.environ, {"PYTHONPATH": "/existing/path"}, clear=False):
            pythonpath = build.build_pythonpath()
        self.assertEqual(pythonpath, os.pathsep.join((str(build.ROOT_DIR), "/existing/path")))

    def test_resolve_python_bin_defaults_to_current_interpreter(self):
        self.assertEqual(build.resolve_python_bin(None), Path(sys.executable).resolve())


if __name__ == "__main__":
    unittest.main()
