#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from betaflight_passthrough import prepare_passthrough
from bundled_tools import build_dfu_env, resolve_dfu_util


FLASHER_ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", FLASHER_ROOT.parent)).resolve()

if str(FLASHER_ROOT) not in sys.path:
    sys.path.insert(0, str(FLASHER_ROOT))

import esptool
import serial

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
FC_DFU_ADDRESS = "0x08000000:leave"
FC_CLI_BAUD = 115200
FC_BOOTLOADER_DELAY = 1.0
FC_REBOOT_DELAY = 5.0


class FlashStepError(RuntimeError):
    def __init__(self, step, exc, details=None):
        self.step = step
        self.exc = exc
        self.details = details or {}
        super().__init__(self._build_message())

    def _build_message(self):
        detail_parts = [f"{key}={value}" for key, value in self.details.items()]
        detail_suffix = f" ({', '.join(detail_parts)})" if detail_parts else ""
        return (
            f"{self.step} failed{detail_suffix}: "
            f"{type(self.exc).__name__}: {self.exc}"
        )


def parse_address(value):
    return int(value, 0)


def resource_path(*parts):
    return RESOURCE_ROOT.joinpath(*parts)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Flash ELRS RX/TX binaries or Betaflight FC binaries."
    )
    parser.add_argument("--target", choices=("rx", "tx", "fc"), required=True)
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=None)
    parser.add_argument("--bin-root", default=".")
    parser.add_argument("--chip", choices=CHIPS, default=None)
    parser.add_argument("--passthrough", action="store_true")
    parser.add_argument("--firmware", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--dfu-util", default=None)
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


def wrap_step(step, func, details=None):
    try:
        return func()
    except FlashStepError:
        raise
    except Exception as exc:
        raise FlashStepError(step, exc, details) from exc


def should_retry_linux_passthrough(exc):
    if not sys.platform.startswith("linux"):
        return False
    if not isinstance(exc, FlashStepError):
        return False
    if exc.step != "Enable Betaflight serial passthrough":
        return False

    root_exc = exc.exc
    errno_value = getattr(root_exc, "errno", None)
    if errno_value == 22:
        return True

    message = str(root_exc)
    return "Invalid argument" in message or "(22," in message


def stream_subprocess_output(cmd, env):
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    chunks = []
    assert process.stdout is not None
    while True:
        chunk = process.stdout.read1(4096)
        if chunk:
            chunks.append(chunk)
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            continue
        if process.poll() is not None:
            break
    return process.wait(), b"".join(chunks).decode("utf-8", errors="ignore")


def run_dfu_flash(dfu_util, firmware):
    cmd = [
        str(dfu_util),
        "-a",
        "0",
        "-s",
        FC_DFU_ADDRESS,
        "-D",
        str(firmware),
    ]
    returncode, output = stream_subprocess_output(cmd, build_dfu_env(dfu_util))
    success_markers = (
        "File downloaded successfully",
        "Submitting leave request",
    )
    leave_errors = (
        "Error during download get_status",
        "Error during special command \"LEAVE\" get_status",
    )
    if returncode == 0:
        return
    if all(marker in output for marker in success_markers) and any(
        marker in output for marker in leave_errors
    ):
        print("dfu-util lost the device during leave; continuing.")
        return

    raise subprocess.CalledProcessError(
        returncode,
        cmd,
        output=output,
    )


def open_fc_serial(port, baud):
    return serial.Serial(
        port=port,
        baudrate=baud,
        timeout=1,
        write_timeout=1,
    )


def has_cli_prompt(response):
    return "# " in response or response.rstrip().endswith("#")


def read_cli_response(serial_port, timeout):
    response = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if serial_port.in_waiting:
            chunk = serial_port.read(serial_port.in_waiting).decode("utf-8", errors="ignore")
            response += chunk
            if has_cli_prompt(response):
                break
        time.sleep(0.01)
    return response


def enter_fc_cli(serial_port):
    serial_port.reset_input_buffer()
    serial_port.reset_output_buffer()
    serial_port.write(b"#")
    serial_port.flush()
    time.sleep(0.3)
    response = read_cli_response(serial_port, 2.0)
    if not has_cli_prompt(response):
        raise RuntimeError("Failed to enter Betaflight CLI")


def connect_fc_cli(port, baud, timeout):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        serial_port = None
        try:
            serial_port = open_fc_serial(port, baud)
            enter_fc_cli(serial_port)
            return serial_port
        except Exception as exc:
            last_error = exc
            if serial_port is not None and serial_port.is_open:
                serial_port.close()
            time.sleep(0.5)
    raise RuntimeError(f"Could not connect to FC CLI on {port}: {last_error}")


def send_fc_command(serial_port, command, timeout=3.0, expect_prompt=True):
    serial_port.write(f"{command}\r\n".encode("utf-8"))
    serial_port.flush()
    if not expect_prompt:
        time.sleep(0.2)
        return ""
    response = read_cli_response(serial_port, timeout)
    if not has_cli_prompt(response):
        raise RuntimeError(f"No CLI prompt after command: {command}")
    return response


def print_cli_response(command, response):
    for line in response.splitlines():
        line = line.strip()
        if not line or line == "#" or line == "# ":
            continue
        if line.startswith(command):
            continue
        print(line)


def load_config_commands(config_file):
    with config_file.open("r", encoding="utf-8") as handle:
        return [
            line.strip()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        ]


def put_fc_in_bootloader(port, baud):
    print("Connecting to FC CLI...")
    serial_port = connect_fc_cli(port, baud, 10.0)
    try:
        print("> bl")
        send_fc_command(serial_port, "bl", expect_prompt=False)
    finally:
        serial_port.close()
    time.sleep(FC_BOOTLOADER_DELAY)


def apply_fc_config(port, baud, config_file):
    commands = load_config_commands(config_file)
    if not commands:
        raise ValueError(f"Config file is empty: {config_file}")

    print("Reconnecting to FC CLI for config...")
    serial_port = connect_fc_cli(port, baud, 20.0)
    try:
        for command in commands:
            print(f"> {command}")
            response = send_fc_command(serial_port, command)
            print_cli_response(command, response)
        print("> save")
        send_fc_command(serial_port, "save", expect_prompt=False)
    finally:
        if serial_port.is_open:
            serial_port.close()


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
    if args.target == "fc" and args.passthrough:
        raise ValueError("--passthrough is not supported for fc")
    if args.target != "fc" and args.config is not None:
        raise ValueError("--config is only supported for target fc")
    if args.target != "fc" and args.dfu_util is not None:
        raise ValueError("--dfu-util is only supported for target fc")

    if args.target == "fc":
        cli_baud = args.baud if args.baud is not None else FC_CLI_BAUD
        if args.firmware is None:
            raise ValueError("--firmware is required for target fc")
        if args.config is None:
            raise ValueError("--config is required for target fc")

        firmware = Path(args.firmware).expanduser().resolve()
        config_file = Path(args.config).expanduser().resolve()
        dfu_util = resolve_dfu_util(args.dfu_util, resource_path("flasher", "vendor", "dfu-util"))

        if not firmware.exists():
            raise FileNotFoundError(f"Firmware not found: {firmware}")
        if not config_file.exists():
            raise FileNotFoundError(f"Config not found: {config_file}")

        print(f"Firmware: {firmware}")
        print(f"Config: {config_file}")
        print(f"Port: {args.port} @ {cli_baud}")
        print(f"DFU util: {dfu_util}")

        fc_details = {
            "target": args.target,
            "port": args.port,
            "baud": cli_baud,
        }
        wrap_step(
            "Enter FC bootloader",
            lambda: put_fc_in_bootloader(args.port, cli_baud),
            fc_details,
        )
        wrap_step(
            "Flash FC firmware over DFU",
            lambda: run_dfu_flash(dfu_util, firmware),
            {**fc_details, "firmware": firmware.name},
        )
        time.sleep(FC_REBOOT_DELAY)
        wrap_step(
            "Apply FC config",
            lambda: apply_fc_config(args.port, cli_baud, config_file),
            {**fc_details, "config": config_file.name},
        )
        return 0

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
        cmd = build_rx_cmd(args.port, baud, chip, firmware, firmware_addr, args.passthrough)

    print(f"Target directory: {target_dir}")
    print(f"Chip: {chip}")
    active_baud = baud
    print(f"Port: {args.port} @ {active_baud}")
    if args.passthrough:
        print("Mode: Betaflight passthrough")

    elrs_details = {
        "target": args.target,
        "port": args.port,
        "baud": active_baud,
        "chip": chip,
        "passthrough": args.passthrough,
    }
    if args.target == "rx" and args.passthrough:
        try:
            wrap_step(
                "Enable Betaflight serial passthrough",
                lambda: prepare_passthrough(args.port, active_baud),
                elrs_details,
            )
        except FlashStepError as exc:
            if should_retry_linux_passthrough(exc) and active_baud == 420000:
                fallback_baud = 230400
                print(
                    "Linux serial driver rejected passthrough baud 420000; "
                    f"retrying at {fallback_baud}."
                )
                active_baud = fallback_baud
                elrs_details["baud"] = active_baud
            else:
                raise
            wrap_step(
                "Enable Betaflight serial passthrough",
                lambda: prepare_passthrough(args.port, active_baud),
                elrs_details,
            )
        cmd = build_rx_cmd(args.port, active_baud, chip, firmware, firmware_addr, args.passthrough)
    wrap_step(
        "Flash ELRS firmware with esptool",
        lambda: esptool.main(cmd),
        elrs_details,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Upload failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
