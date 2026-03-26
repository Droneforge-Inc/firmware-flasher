#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

from betaflight_passthrough import prepare_passthrough


FLASHER_ROOT = Path(__file__).resolve().parent

if str(FLASHER_ROOT) not in sys.path:
    sys.path.insert(0, str(FLASHER_ROOT))

import esptool

BOOTLOADER_ADDR = 0x1000
BOOTLOADER_ADDR_S3 = 0x0000
PARTITIONS_ADDR = 0x8000
APP_SELECT_ADDR = 0xE000
TX_FIRMWARE_ADDR = 0x10000
RX_FIRMWARE_ADDR = 0x0000

BOOTLOADER_NAME = "bootloader.bin"
PARTITIONS_NAME = "partitions.bin"
APP_SELECT_NAME = "boot_app0.bin"
FIRMWARE_NAME = "firmware.bin"

CHIPS = ("esp8266", "esp32", "esp32-c3", "esp32-s3")


def parse_address(value):
    return int(value, 0)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Flash ELRS RX/TX binaries to a USB serial port with vendored esptool."
    )
    parser.add_argument("--target", choices=("rx", "tx"), required=True)
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=None)
    parser.add_argument("--bin-root", default=".")
    parser.add_argument("--chip", choices=CHIPS, default=None)
    parser.add_argument("--passthrough", action="store_true")
    parser.add_argument("--firmware", default=None)
    parser.add_argument("--bootloader", default=None)
    parser.add_argument("--partitions", default=None)
    parser.add_argument("--app-select", default=None)
    parser.add_argument("--firmware-addr", type=parse_address, default=None)
    parser.add_argument("--bootloader-addr", type=parse_address, default=None)
    parser.add_argument("--partitions-addr", type=parse_address, default=PARTITIONS_ADDR)
    parser.add_argument("--app-select-addr", type=parse_address, default=APP_SELECT_ADDR)
    return parser.parse_args()


def resolve_target_dir(target, bin_root):
    target_dir = bin_root / target
    if (target_dir / FIRMWARE_NAME).exists():
        return target_dir
    if (bin_root / FIRMWARE_NAME).exists():
        return bin_root
    return target_dir


def resolve_file(path_arg, directory, default_name):
    if path_arg is not None:
        return Path(path_arg).expanduser().resolve()
    default_path = directory / default_name
    if default_path.exists():
        return default_path
    return None


def default_bootloader_addr(chip):
    if chip in ("esp32-c3", "esp32-s3"):
        return BOOTLOADER_ADDR_S3
    return BOOTLOADER_ADDR


def build_rx_cmd(port, baud, chip, firmware, firmware_addr, passthrough):
    cmd = [
        "--chip",
        chip,
        "--port",
        port,
        "--baud",
        str(baud),
    ]
    if passthrough:
        cmd.extend(["--passthrough", "--before", "no_reset"])
        cmd.extend(["--after", "hard_reset" if chip.startswith("esp32") else "soft_reset"])
    else:
        cmd.extend(["--after", "soft_reset"])
    cmd.extend(["write_flash", hex(firmware_addr), str(firmware)])
    return cmd


def build_tx_cmd(
    port,
    baud,
    chip,
    bootloader,
    bootloader_addr,
    partitions,
    partitions_addr,
    app_select,
    app_select_addr,
    firmware,
    firmware_addr,
):
    return [
        "--chip",
        chip,
        "--port",
        port,
        "--baud",
        str(baud),
        "--after",
        "hard_reset",
        "write_flash",
        "-z",
        "--flash_mode",
        "dio",
        "--flash_freq",
        "40m",
        "--flash_size",
        "detect",
        hex(bootloader_addr),
        str(bootloader),
        hex(partitions_addr),
        str(partitions),
        hex(app_select_addr),
        str(app_select),
        hex(firmware_addr),
        str(firmware),
    ]


def main():
    args = parse_args()
    if args.target == "tx" and args.passthrough:
        raise ValueError("--passthrough is only supported for rx")

    baud = args.baud if args.baud is not None else (420000 if args.passthrough else 460800)
    bin_root = Path(args.bin_root).resolve()
    target_dir = resolve_target_dir(args.target, bin_root)

    firmware = resolve_file(args.firmware, target_dir, FIRMWARE_NAME)
    bootloader = resolve_file(args.bootloader, target_dir, BOOTLOADER_NAME)
    partitions = resolve_file(args.partitions, target_dir, PARTITIONS_NAME)
    app_select = resolve_file(args.app_select, target_dir, APP_SELECT_NAME)

    if args.target == "tx":
        chip = args.chip or "esp32-s3"
        missing = []
        if bootloader is None:
            missing.append(BOOTLOADER_NAME)
        if partitions is None:
            missing.append(PARTITIONS_NAME)
        if app_select is None:
            missing.append(APP_SELECT_NAME)
        if firmware is None:
            missing.append(FIRMWARE_NAME)
        if missing:
            raise FileNotFoundError("TX flashing requires: " + ", ".join(missing))

        bootloader_addr = args.bootloader_addr if args.bootloader_addr is not None else default_bootloader_addr(chip)
        firmware_addr = args.firmware_addr if args.firmware_addr is not None else TX_FIRMWARE_ADDR
        cmd = build_tx_cmd(
            args.port,
            baud,
            chip,
            bootloader,
            bootloader_addr,
            partitions,
            args.partitions_addr,
            app_select,
            args.app_select_addr,
            firmware,
            firmware_addr,
        )
    else:
        chip = args.chip or "esp8266"
        if firmware is None:
            raise FileNotFoundError(f"RX flashing requires {FIRMWARE_NAME}")
        firmware_addr = args.firmware_addr if args.firmware_addr is not None else RX_FIRMWARE_ADDR
        if args.passthrough:
            prepare_passthrough(args.port, baud)
        cmd = build_rx_cmd(args.port, baud, chip, firmware, firmware_addr, args.passthrough)

    print(f"Target directory: {target_dir}")
    print(f"Chip: {chip}")
    print(f"Port: {args.port} @ {baud}")
    if args.passthrough:
        print("Mode: Betaflight passthrough")

    esptool.main(cmd)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Upload failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
