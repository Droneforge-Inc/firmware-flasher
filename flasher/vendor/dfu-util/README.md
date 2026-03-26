Place platform-specific `dfu-util` bundles here so PyInstaller can include them.

Recommended layout:

```text
flasher/vendor/dfu-util/macos-arm64/dfu-util
flasher/vendor/dfu-util/macos-x86_64/dfu-util
flasher/vendor/dfu-util/macos-arm64/libusb-1.0.0.dylib
flasher/vendor/dfu-util/linux-arm64/dfu-util
flasher/vendor/dfu-util/linux-x86_64/dfu-util
flasher/vendor/dfu-util/windows-x86_64/dfu-util.exe
```

The FC flasher checks `--dfu-util` first, then this directory, then `PATH`. On Windows the executable name must be `dfu-util.exe`.
