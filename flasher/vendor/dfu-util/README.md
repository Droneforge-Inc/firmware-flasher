Place platform-specific `dfu-util` bundles here so PyInstaller can include them.

Recommended layout (put **libusb next to the tool** for each platform):

```text
flasher/vendor/dfu-util/macos-arm64/dfu-util
flasher/vendor/dfu-util/macos-arm64/libusb-1.0.0.dylib
flasher/vendor/dfu-util/macos-x86_64/dfu-util
flasher/vendor/dfu-util/macos-x86_64/libusb-1.0.0.dylib
flasher/vendor/dfu-util/linux-arm64/dfu-util
flasher/vendor/dfu-util/linux-arm64/libusb-1.0.so.0
flasher/vendor/dfu-util/linux-x86_64/dfu-util
flasher/vendor/dfu-util/linux-x86_64/libusb-1.0.so.0
flasher/vendor/dfu-util/windows-x86_64/dfu-util.exe
flasher/vendor/dfu-util/windows-x86_64/libusb-1.0.dll
```

When launched via Nimbus stage layout instead:

```text
stage/bin/dfu-util
stage/lib/libusb-1.0.so*   # or .dylib / next to .exe on Windows
```

`bundled_tools.build_dfu_env()` prepends library search paths in this order:

1. sibling `../lib` (Nimbus stage)
2. the tool directory (vendored + Windows DLL-next-to-exe)

so ambient host/Nix/conda `libusb` cannot steal the dependency.

The FC flasher checks `--dfu-util` first, then this directory, then `PATH`.
On Windows the executable name must be `dfu-util.exe`.
