import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bundled_tools


class RuntimePathTests(unittest.TestCase):
    def test_dfu_search_paths_windows(self):
        paths = bundled_tools.dfu_search_paths(
            Path("/bundle/flasher/vendor/dfu-util"),
            platform_name="Windows",
            machine_name="AMD64",
            os_name="nt",
        )

        self.assertEqual(paths[0], Path("/bundle/flasher/vendor/dfu-util/windows-x86_64/dfu-util.exe"))

    def test_dfu_search_paths_macos_prefers_macos_alias(self):
        paths = bundled_tools.dfu_search_paths(
            Path("/bundle/flasher/vendor/dfu-util"),
            platform_name="Darwin",
            machine_name="arm64",
            os_name="posix",
        )

        self.assertEqual(paths[0], Path("/bundle/flasher/vendor/dfu-util/macos-arm64/dfu-util"))
        self.assertEqual(paths[1], Path("/bundle/flasher/vendor/dfu-util/darwin-arm64/dfu-util"))

    def test_resolve_dfu_util_falls_back_to_path(self):
        with mock.patch.object(bundled_tools, "first_existing", return_value=None):
            with mock.patch.object(bundled_tools.shutil, "which", return_value="/usr/bin/dfu-util"):
                resolved = bundled_tools.resolve_dfu_util(None, Path("/bundle/flasher/vendor/dfu-util"))

        self.assertEqual(resolved, Path("/usr/bin/dfu-util"))

    def test_dfu_library_dirs_stage_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            lib_dir = root / "lib"
            bin_dir.mkdir()
            lib_dir.mkdir()
            dfu = bin_dir / "dfu-util"
            dfu.write_text("")

            dirs = bundled_tools.dfu_library_dirs(dfu)
            self.assertEqual(dirs[0], str(lib_dir.resolve()))
            self.assertEqual(dirs[1], str(bin_dir.resolve()))

    def test_dfu_library_dirs_vendor_layout_tool_dir_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_dir = Path(tmp) / "macos-arm64"
            tool_dir.mkdir()
            dfu = tool_dir / "dfu-util"
            dfu.write_text("")
            # No sibling lib/ — only tool dir should be returned.
            dirs = bundled_tools.dfu_library_dirs(dfu)
            self.assertEqual(dirs, [str(tool_dir.resolve())])

    def test_build_dfu_env_prefers_sibling_lib_then_tool_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            lib_dir = root / "lib"
            bin_dir.mkdir()
            lib_dir.mkdir()
            dfu = bin_dir / "dfu-util"
            dfu.write_text("")

            with mock.patch.dict("os.environ", {"LD_LIBRARY_PATH": "/host/lib"}, clear=False):
                env = bundled_tools.build_dfu_env(
                    dfu, platform_name="linux", os_name="posix"
                )

            ld = env["LD_LIBRARY_PATH"].split(os.pathsep)
            self.assertEqual(ld[0], str(lib_dir.resolve()))
            self.assertEqual(ld[1], str(bin_dir.resolve()))
            self.assertIn("/host/lib", ld)

    def test_build_dfu_env_windows_prepends_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_dir = Path(tmp) / "windows-x86_64"
            tool_dir.mkdir()
            dfu = tool_dir / "dfu-util.exe"
            dfu.write_text("")

            with mock.patch.dict("os.environ", {"PATH": "/host/bin"}, clear=False):
                env = bundled_tools.build_dfu_env(
                    dfu, platform_name="win32", os_name="nt"
                )

            path_parts = env["PATH"].split(os.pathsep)
            self.assertEqual(path_parts[0], str(tool_dir.resolve()))
            self.assertIn("/host/bin", path_parts)

    def test_build_dfu_env_darwin_uses_dyld(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_dir = Path(tmp) / "macos-arm64"
            tool_dir.mkdir()
            dfu = tool_dir / "dfu-util"
            dfu.write_text("")

            with mock.patch.dict("os.environ", {"DYLD_LIBRARY_PATH": "/host/lib"}, clear=False):
                env = bundled_tools.build_dfu_env(
                    dfu, platform_name="darwin", os_name="posix"
                )

            dyld = env["DYLD_LIBRARY_PATH"].split(os.pathsep)
            self.assertEqual(dyld[0], str(tool_dir.resolve()))
            self.assertIn("/host/lib", dyld)


if __name__ == "__main__":
    unittest.main()
