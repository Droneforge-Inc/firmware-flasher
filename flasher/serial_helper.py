import time


ENCODING = "utf-8"


class SerialHelper:
    def __init__(self, serial, timeout=2.0, delimiters=None):
        self.serial = serial
        self.timeout = timeout
        self.buf = bytearray()
        self.set_delimiters(delimiters or ["\n", "CCC"])

    def set_serial(self, serial):
        self.serial = serial

    def set_timeout(self, timeout):
        self.timeout = timeout

    def set_delimiters(self, delimiters):
        self.delimiters = [
            d.encode(ENCODING) if isinstance(d, str) else d for d in delimiters
        ]

    def clear(self):
        self.serial.reset_input_buffer()
        self.buf = bytearray()

    def read_line(self, timeout=None):
        if timeout is None or timeout <= 0.0:
            timeout = self.timeout

        start = time.time()
        while (time.time() - start) < timeout:
            for delimiter in self.delimiters:
                idx = self.buf.find(delimiter)
                if idx >= 0:
                    end = idx + len(delimiter)
                    data = bytes(self.buf[:end])
                    self.buf = self.buf[end:]
                    try:
                        return data.decode(ENCODING)
                    except UnicodeDecodeError:
                        return ""

            size = max(0, min(2048, self.serial.in_waiting))
            data = self.serial.read(size)
            if data:
                self.buf.extend(data)

        self.buf = bytearray()
        return ""

    def write(self, data):
        if isinstance(data, str):
            data = data.encode(ENCODING)
        self.serial.write(data)
        self.serial.flush()

    def write_line(self, data):
        if isinstance(data, bytes):
            self.write(data + b"\r\n")
        else:
            self.write(f"{data}\r\n")
