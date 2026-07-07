def modbus_crc16(data: bytes) -> bytes:
    """
    Calculate Modbus RTU CRC16 for the given data.

    Uses polynomial 0xA001 and initial value 0xFFFF.
    Returns the CRC as 2 bytes in little-endian format (low byte first).

    Args:
        data: The input data bytes to calculate CRC for.

    Returns:
        2 bytes representing the CRC16 in little-endian format.
    """
    crc = 0xFFFF

    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1

    # Return as little-endian bytes (low byte first, high byte second)
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])
