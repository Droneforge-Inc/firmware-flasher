import re
import time

import serial

from bootloader import get_init_seq
from serial_helper import SerialHelper


class PassthroughEnabled(Exception):
    pass


class PassthroughFailed(Exception):
    pass


def _validate_serialrx(helper, config, expected):
    if isinstance(expected, str):
        expected = [expected]
    helper.set_delimiters(["# "])
    helper.clear()
    helper.write_line(f"get {config}")
    line = helper.read_line(1.0).strip()
    return any(f" = {value}" in line for value in expected)


def bf_passthrough_init(port, requested_baudrate):
    serial_port = serial.Serial(
        port=port,
        baudrate=115200,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=1,
        xonxoff=0,
        rtscts=0,
    )
    helper = SerialHelper(serial_port, 3.0, ["CCC", "# "])
    helper.clear()
    helper.write("#")
    start = helper.read_line(2.0).strip()

    if "CCC" in start:
        serial_port.close()
        raise PassthroughEnabled("Passthrough already enabled and bootloader active")
    if not start or not start.endswith("#"):
        serial_port.close()
        raise PassthroughEnabled("No Betaflight CLI prompt detected")

    checks = []
    if not _validate_serialrx(helper, "serialrx_provider", ["CRSF", "ELRS"]):
        checks.append("serialrx_provider must be CRSF/ELRS")
    if not _validate_serialrx(helper, "serialrx_inverted", "OFF"):
        checks.append("serialrx_inverted must be OFF")
    if not _validate_serialrx(helper, "serialrx_halfduplex", ["OFF", "AUTO"]):
        checks.append("serialrx_halfduplex must be OFF/AUTO")

    if checks:
        serial_port.close()
        raise PassthroughFailed("; ".join(checks))

    helper.set_delimiters(["\n"])
    helper.clear()
    helper.write_line("serial")

    serial_rx_index = ""
    while True:
        line = helper.read_line().strip()
        if not line or "#" in line:
            break
        match = re.search(r"serial ((?:UART)?[0-9]+) ([0-9]+) ", line)
        if match and (int(match.group(2)) & 64) == 64:
            serial_rx_index = match.group(1)
            break

    if not serial_rx_index:
        serial_port.close()
        raise PassthroughFailed("Could not find Betaflight Serial RX UART")

    helper.write_line(f"serialpassthrough {serial_rx_index} {requested_baudrate}")
    time.sleep(0.2)
    serial_port.close()


def reset_rx_to_bootloader(port, baudrate):
    bootloader_seq = get_init_seq("CRSF", "ESP82")

    serial_port = serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=1,
        xonxoff=0,
        rtscts=0,
    )
    helper = SerialHelper(serial_port, 3.0)
    helper.clear()
    helper.write(b"\x07\x07\x12\x20" + (32 * b"\x55"))
    time.sleep(0.2)
    helper.write(bootloader_seq)
    serial_port.flush()
    time.sleep(0.5)
    serial_port.close()


def prepare_passthrough(port, passthrough_baudrate, host_baudrate=None):
    if host_baudrate is None:
        host_baudrate = passthrough_baudrate
    try:
        bf_passthrough_init(port, passthrough_baudrate)
    except PassthroughEnabled:
        pass
    time.sleep(0.3)
    reset_rx_to_bootloader(port, host_baudrate)
