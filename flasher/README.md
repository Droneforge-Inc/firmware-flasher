# ELRS Flasher

Self-contained Python flasher for ELRS TX and RX targets.

Files:
- `simple_usb_upload.py`: CLI entrypoint
- `betaflight_passthrough.py`: RX Betaflight passthrough setup
- `bootloader.py`: CRSF bootloader reset sequence
- `serial_helper.py`: small serial helper
- `esptool/`: vendored `esptool` package
- `flash-helper.spec`: PyInstaller onefile build
- `requirements-build.txt`: build-time dependencies

## Build

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-build.txt
pyinstaller --clean --noconfirm flash-helper.spec
```

Output:

```bash
dist/flash-helper
```

## macOS universal2

`target_arch="universal2"` is already set in `flash-helper.spec`.

That build only works if the Python used to create `.venv` is itself `universal2`.

Example:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-build.txt
pyinstaller --clean --noconfirm flash-helper.spec
```

If your Python is arm64-only or x86_64-only, change:

```py
target_arch="universal2"
```

to:

```py
target_arch=None
```

in `flash-helper.spec`.

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
