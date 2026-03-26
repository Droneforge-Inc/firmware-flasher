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


if __name__ == "__main__":
    unittest.main()
