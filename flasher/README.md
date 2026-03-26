# ELRS Flasher

Self-contained Python flasher for ELRS TX/RX targets and Betaflight FC targets.

Files:
- `simple_usb_upload.py`: CLI entrypoint
- `betaflight_passthrough.py`: RX Betaflight passthrough setup
- `bootloader.py`: CRSF bootloader reset sequence
- `serial_helper.py`: small serial helper
- `esptool/`: vendored `esptool` package
- `vendor/dfu-util/`: optional vendored `dfu-util` bundle for FC flashing
- `flash-helper.spec`: PyInstaller onefile build
- `requirements-build.txt`: build-time dependencies

## Build

From this directory:

```bash
./build.sh --mode native
```

Output:

```bash
dist/flash-helper
```

## macOS universal2

Universal builds require a `universal2` Python.

Example:

```bash
./build.sh --mode universal --python /Library/Frameworks/Python.framework/Versions/3.12/bin/python3
```

If your vendored `dfu-util` is single-arch, the FC path is only self-contained on that matching arch even if the main executable is `universal2`.

## Usage

Default TX flash:

```bash
dist/flash-helper --target tx --port /dev/cu.usbmodem11401 --bin-root /path/to/tx/build
```

Default RX flash:

```bash
dist/flash-helper --target rx --port /dev/cu.usbmodem11401 --bin-root /path/to/rx/build
```

RX via Betaflight passthrough:

```bash
dist/flash-helper --target rx --port /dev/cu.usbmodem11401 --bin-root /path/to/rx/build --passthrough
```

FC flash:

```bash
dist/flash-helper --target fc --port /dev/cu.usbmodem11401 \
  --firmware /path/to/betafpv.bin --config /path/to/whoop-of.txt
```

## Defaults

TX defaults:
- chip: `esp32-s3`
- `bootloader.bin` at `0x0000`
- `partitions.bin` at `0x8000`
- `boot_app0.bin` at `0xe000`
- `firmware.bin` at `0x10000`

RX defaults:
- chip: `esp8266`
- `firmware.bin` at `0x0000`

`--passthrough` is RX-only.

FC defaults:
- `--firmware` is required
- `--config` is required
- `--dfu-util` overrides the bundled/system `dfu-util` path

## Vendored dfu-util

To make FC flashing self-contained inside the PyInstaller app, place platform-specific `dfu-util` files under:

```text
flasher/vendor/dfu-util/
```

Example macOS arm64 layout:

```text
flasher/vendor/dfu-util/macos-arm64/dfu-util
flasher/vendor/dfu-util/macos-arm64/libusb-1.0.0.dylib
```

At runtime the flasher checks `--dfu-util` first, then the bundled vendor directory, then `PATH`.
