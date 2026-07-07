from goodwe_dt_lib.crc import modbus_crc16
from goodwe_dt_lib.exceptions import RequestFailedException, PartialResponseException


def test_crc_runtime_request():
    # real DT runtime read request body 7f 03 7594 0049, CRC appended = d5c2
    assert modbus_crc16(bytes.fromhex("7f0375940049")) == bytes.fromhex("d5c2")


def test_crc_meter_request():
    # real DT meter read request body 7f 03 75f3 000f, CRC appended = e5ef
    assert modbus_crc16(bytes.fromhex("7f0375f3000f")) == bytes.fromhex("e5ef")


def test_request_failed_carries_count():
    ex = RequestFailedException("no response", 3)
    assert ex.consecutive_failures_count == 3


def test_partial_response_fields():
    ex = PartialResponseException(10, 30)
    assert ex.length == 10 and ex.expected == 30
