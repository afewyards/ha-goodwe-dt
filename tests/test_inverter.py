"""Golden zero-diff tests for DtInverter decode + device-info decode."""

import json
from pathlib import Path

# Adjust import path: the lib is installed as a package via pyproject.toml
from goodwe_dt_lib.inverter import DtInverter
from goodwe_dt_lib.modbus import parse_response

BASE = json.loads((Path(__file__).resolve().parent.parent / "docs/gw_baseline.json").read_text())
RUNTIME_FRAME = bytes.fromhex(BASE["raw_frames"][0])
METER_FRAME   = bytes.fromhex(BASE["raw_frames"][1])
DEV = json.loads((Path(__file__).resolve().parent.parent / "docs/gw_device_info.json").read_text())
DEV_FRAMES = [l.split("Received:",1)[1].strip() for l in DEV["frames"] if l.startswith("Received:")]


def test_runtime_decode_matches_baseline_zero_diff():
    inv = DtInverter("x")
    rp = parse_response(RUNTIME_FRAME, 73)
    mp = parse_response(METER_FRAME, 15)
    ours = inv._decode_runtime(rp, mp)
    # normalize datetimes the same way the baseline was saved
    ours_norm = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in ours.items()}
    expected = {k: v for k, v in BASE["decoded"].items() if k != "leakage_current"}
    assert set(ours_norm) == set(expected)          # 51 ids
    for k in expected:
        assert ours_norm[k] == expected[k], f"mismatch on {k}: {ours_norm[k]!r} != {expected[k]!r}"


def test_device_info_decode():
    version_payload = parse_response(bytes.fromhex(DEV_FRAMES[0]), 40)
    serial, firmware, model = DtInverter._decode_device_info(version_payload)
    assert serial == "53000DSC243W0249"
    assert firmware == "4.5.0b"
    # this unit's version frame has 0xFF model bytes -> model falls back to MODEL_CMD
    assert model is None
    model_payload = parse_response(bytes.fromhex(DEV_FRAMES[1]), 8)
    assert model_payload[0:16].decode("ascii", "ignore").rstrip("\x00").strip() == "GW3000-DNS-30"
