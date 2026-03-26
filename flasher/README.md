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
- `build.py`: cross-platform build entrypoint
- `requirements-build.txt`: build-time dependencies

## Build

The canonical build entrypoint is `build.py`. It works on macOS, Linux, and Windows and builds a native binary for the current OS.

macOS / Linux:

```bash
python3 build.py --mode native
```

Windows PowerShell:

```powershell
py -3 .\build.py --mode native
```

Convenience wrappers:

```bash
./build.sh --mode native
```

```powershell
.\build.ps1 --mode native
```

Outputs:

```text
macOS/Linux: dist/flash-helper
Windows:     dist/flash-helper.exe
```

Options:

```text
--python PATH                  Python interpreter to use for the venv
--venv PATH                    Venv directory to create/use
--pyinstaller-config-dir PATH  PyInstaller config directory
```

## macOS universal2

`--mode universal` is macOS-only and requires a `universal2` Python interpreter.

Example:

```bash
python3 build.py --mode universal --python /Library/Frameworks/Python.framework/Versions/3.12/bin/python3
```

This maps to a PyInstaller `universal2` build.

If your vendored `dfu-util` is single-arch, the FC path is only self-contained on that matching arch even if the main executable is `universal2`.

## CI

GitHub Actions builds native artifacts on macOS, Linux, and Windows. The workflow also runs:

- `python -m unittest discover -s tests`
- a `--help` smoke test against the built binary

## Usage

Default TX flash on macOS:

```bash
dist/flash-helper --target tx --port /dev/cu.usbmodem11401 --bin-root /path/to/tx/build
```

Default TX flash on Linux:

```bash
dist/flash-helper --target tx --port /dev/ttyUSB0 --bin-root /path/to/tx/build
```

Default TX flash on Windows:

```powershell
dist\flash-helper.exe --target tx --port COM3 --bin-root C:\path\to\tx\build
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

Windows FC flash:

```powershell
dist\flash-helper.exe --target fc --port COM3 `
  --firmware C:\path\to\betafpv.bin --config C:\path\to\whoop-of.txt
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

Example layouts:

```text
flasher/vendor/dfu-util/macos-arm64/dfu-util
flasher/vendor/dfu-util/macos-arm64/libusb-1.0.0.dylib
flasher/vendor/dfu-util/linux-x86_64/dfu-util
flasher/vendor/dfu-util/windows-x86_64/dfu-util.exe
```

At runtime the flasher checks `--dfu-util` first, then the bundled vendor directory, then `PATH`.
