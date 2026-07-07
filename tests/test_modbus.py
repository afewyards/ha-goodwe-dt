import json
from pathlib import Path
import pytest
from goodwe_dt_lib.modbus import build_read_request, build_write_request, parse_response, parse_write_response
from goodwe_dt_lib.exceptions import PartialResponseException, RequestRejectedException

BASE = json.loads((Path(__file__).resolve().parent.parent / "docs/gw_baseline.json").read_text())
RUNTIME = bytes.fromhex(BASE["raw_frames"][0])   # aa55...92... 153 bytes, 73 regs
METER   = bytes.fromhex(BASE["raw_frames"][1])   # aa55...1e... 37 bytes, 15 regs

def test_build_runtime_request():
    assert build_read_request(0x7f, 0x7594, 0x49) == bytes.fromhex("7f0375940049d5c2")

def test_build_meter_request():
    assert build_read_request(0x7f, 0x75f3, 0x0f) == bytes.fromhex("7f0375f3000fe5ef")

def test_parse_runtime_ok():
    payload = parse_response(RUNTIME, 73)
    assert len(payload) == 146
    assert payload[:6] == RUNTIME[5:11]   # timestamp bytes, payload starts after 5-byte header

def test_parse_meter_ok():
    assert len(parse_response(METER, 15)) == 30

def test_parse_truncated_raises_partial():
    with pytest.raises(PartialResponseException):
        parse_response(RUNTIME[:20], 73)

def test_parse_bad_crc_raises_rejected():
    bad = bytearray(RUNTIME); bad[-1] ^= 0xFF
    with pytest.raises(RequestRejectedException):
        parse_response(bytes(bad), 73)

def test_parse_wrong_length_frame_rejected():
    # runtime frame received when a 15-reg meter frame was expected (cross-talk)
    with pytest.raises(RequestRejectedException):
        parse_response(RUNTIME, 15)

def test_parse_concatenated_returns_first_frame():
    # two frames glued (observed cross-talk); expecting the first (73-reg) one
    glued = RUNTIME + METER
    assert len(parse_response(glued, 73)) == 146

def test_build_write_request_export_limit_10():
    # write reg 40336 (0x9d90) = 10 ; CRC16(0x7f069d90000a)=2c52 little-endian
    assert build_write_request(0x7f, 0x9d90, 10) == bytes.fromhex("7f069d90000a2c52")

def test_build_write_request_zero_and_max():
    assert build_write_request(0x7f, 0x9d90, 0) == bytes.fromhex("7f069d900000ac55")
    assert build_write_request(0x7f, 0x9d90, 100) == bytes.fromhex("7f069d900064adbe")

def test_parse_write_response_ok_wrapped():
    # aa55 + echo(7f069d90000a) + crc(2c52) — the expected happy path
    parse_write_response(bytes.fromhex("aa557f069d90000a2c52"), 0x9d90, 10)  # no raise

def test_parse_write_response_ok_unwrapped():
    parse_write_response(bytes.fromhex("7f069d90000a2c52"), 0x9d90, 10)  # no raise

def test_parse_write_response_wrong_value_raises():
    with pytest.raises(RequestRejectedException):
        parse_write_response(bytes.fromhex("aa557f069d90000a2c52"), 0x9d90, 11)

def test_parse_write_response_bad_crc_raises():
    bad = bytearray(bytes.fromhex("aa557f069d90000a2c52")); bad[-1] ^= 0xFF
    with pytest.raises(RequestRejectedException):
        parse_write_response(bytes(bad), 0x9d90, 10)
