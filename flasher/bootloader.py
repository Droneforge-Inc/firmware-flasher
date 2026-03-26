INIT_SEQ = {
    "CRSF": [0xEC, 0x04, 0x32, ord("b"), ord("l")],
    "GHST": [0x89, 0x04, 0x32, ord("b"), ord("l")],
}


def calc_crc8(payload, poly=0xD5):
    crc = 0
    for data in payload:
        crc ^= data
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ poly
            else:
                crc = crc << 1
    return crc & 0xFF


def get_telemetry_seq(seq, key=None):
    payload = list(seq)
    if payload:
        if key:
            if isinstance(key, str):
                key = [ord(ch) for ch in key]
            payload += key
            payload[1] += len(key)
        payload += [calc_crc8(payload[2:])]
    return bytes(payload)


def get_init_seq(module, key=None):
    return get_telemetry_seq(INIT_SEQ.get(module, []), key)
