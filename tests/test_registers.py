import json
from pathlib import Path
from goodwe_dt_lib import registers as R
from goodwe_dt_lib import const as C

EXPECTED = set(json.loads((Path(__file__).resolve().parent.parent / "docs/gw_baseline.json").read_text())["decoded"]) - {"leakage_current"}

def all_ids():
    return {s.id_ for s in (*R.RUNTIME_SENSORS, *R.METER_SENSORS, *R.CALCULATED_SENSORS)}

def test_full_id_set_matches_51():
    ids = all_ids()
    assert ids == EXPECTED
    assert len(ids) == 51

def test_no_leakage_current():
    assert "leakage_current" not in all_ids()

def test_offsets_spotcheck():
    by = {s.id_: s for s in R.RUNTIME_SENSORS}
    assert by["vpv1"].offset == 6
    assert by["apparent_power"].offset == 66 and by["apparent_power"].size_ == 4
    assert by["e_total"].offset == 90
    mby = {s.id_: s for s in R.METER_SENSORS}
    assert mby["meter_active_power"].offset == 0

def test_commands():
    assert C.RUNTIME_CMD == (0x7594, 0x49)
    assert C.METER_CMD == (0x75f3, 0x0f)
    assert C.MODBUS_ADDR == 0x7f

def test_label_maps_present():
    assert C.WORK_MODES and C.SAFETY_COUNTRIES and C.DERATING_MODE_CODES and C.METER_COMMUNICATION_STATUS
    assert C.WORK_MODES.get(1) == "Normal"
