"""Modbus RTU request building and AA55 response parsing."""

from .crc import modbus_crc16
from .exceptions import (
    PartialResponseException,
    RequestRejectedException,
)


def build_read_request(addr: int, reg: int, count: int) -> bytes:
    """
    Build a Modbus RTU read holding registers request.

    Args:
        addr: Slave address (1 byte).
        reg: Starting register address (16-bit, big-endian).
        count: Number of registers to read (16-bit, big-endian).

    Returns:
        Modbus RTU request frame: addr(1) func(1) reg_hi reg_lo cnt_hi cnt_lo crc_lo crc_hi.
    """
    func = 0x03  # Read holding registers

    # Build the request without CRC
    request = bytes([
        addr,
        func,
        (reg >> 8) & 0xFF,      # reg_hi
        reg & 0xFF,              # reg_lo
        (count >> 8) & 0xFF,    # cnt_hi
        count & 0xFF,            # cnt_lo
    ])

    # Calculate and append CRC
    crc = modbus_crc16(request)
    return request + crc


def build_write_request(addr: int, reg: int, value: int) -> bytes:
    """Build a Modbus func 0x06 (write single holding register) frame.

    Frame: addr(1) func(1)=0x06 reg_hi reg_lo val_hi val_lo crc_lo crc_hi.
    ``value`` is written as an unsigned 16-bit big-endian word.
    """
    value &= 0xFFFF
    request = bytes([
        addr,
        0x06,                    # write single register
        (reg >> 8) & 0xFF,
        reg & 0xFF,
        (value >> 8) & 0xFF,
        value & 0xFF,
    ])
    return request + modbus_crc16(request)


def parse_response(raw: bytes, expected_count: int) -> bytes:
    """
    Parse an AA55-wrapped Modbus RTU response.

    Args:
        raw: Raw response bytes, potentially concatenated with other frames.
        expected_count: Expected number of registers to receive.

    Returns:
        The payload (register data, length == expected_count*2) on success.

    Raises:
        RequestRejectedException: If response is malformed, has wrong func, wrong length, or bad CRC.
        PartialResponseException: If response is truncated (less than expected total).
    """
    # Validation 1: response too short
    if len(raw) <= 4:
        raise RequestRejectedException("response too short")

    # Read func and bytecount from the frame
    func = raw[3]
    bytecount = raw[4]
    expected_total = bytecount + 7

    # Validation 2: check if we have enough bytes for the complete frame
    if len(raw) < expected_total:
        raise PartialResponseException(len(raw), expected_total)

    # Validation 3: verify CRC (computed over raw[2:expected_total-2])
    crc_data = raw[2 : expected_total - 2]
    computed_crc = modbus_crc16(crc_data)
    received_crc = raw[expected_total - 2 : expected_total]

    if computed_crc != received_crc:
        raise RequestRejectedException("crc mismatch")

    # Validation 4: check function code
    if func != 0x03:
        raise RequestRejectedException("modbus failure / wrong frame")

    # Validation 5: check payload length matches expected
    if bytecount != expected_count * 2:
        raise RequestRejectedException("unexpected length")

    # Return the payload (register data)
    return raw[5 : 5 + bytecount]


def parse_write_response(raw: bytes, reg: int, value: int) -> None:
    """Validate the inverter's echo of a func 0x06 write.

    Accepts the echo with or without the ``aa55`` wrapper. Verifies func code,
    echoed register + value, and CRC16 over the 6 body bytes. Raises
    ``RequestRejectedException`` on any mismatch.
    """
    frame = raw[2:] if raw[:2] == b"\xaa\x55" else raw
    if len(frame) < 8:
        raise RequestRejectedException("write echo too short")
    body, crc = frame[:6], frame[6:8]
    if modbus_crc16(body) != crc:
        raise RequestRejectedException("write echo crc mismatch")
    if body[1] != 0x06:
        raise RequestRejectedException("write echo wrong func")
    echoed_reg = (body[2] << 8) | body[3]
    echoed_val = (body[4] << 8) | body[5]
    if echoed_reg != reg or echoed_val != (value & 0xFFFF):
        raise RequestRejectedException(
            f"write echo mismatch reg={echoed_reg:#06x} val={echoed_val}"
        )
