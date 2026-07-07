from goodwe_dt_lib.sensors import (
    ProtocolResponse,
    SensorKind,
    Voltage,
    Current,
    Frequency,
    Temp,
    Power4,
    Power4S,
    PowerS,
    Apparent4,
    Reactive4,
    Energy,
    Energy4,
    Energy4W,
    Integer,
    Long,
    Decimal,
    Timestamp,
    Enum2,
    EnumBitmap4,
)


def rd(hexs):
    return ProtocolResponse(bytes.fromhex(hexs))


# --- ProtocolResponse ---


def test_protocol_response_seek_read():
    resp = rd("0102030405")
    resp.seek(2)
    assert resp.read(2) == bytes.fromhex("0304")


# --- Voltage ---


def test_voltage():
    assert Voltage("v", 0, "V", SensorKind.PV).read(rd("0539")) == 133.7


def test_voltage_sentinel():
    assert Voltage("v", 0, "V", SensorKind.PV).read(rd("ffff")) == 0


def test_voltage_unit():
    s = Voltage("v", 0, "V", SensorKind.PV)
    assert s.unit == "V"
    assert s.size_ == 2


# --- Current ---


def test_current():
    assert Current("i", 0, "A", SensorKind.PV).read(rd("0005")) == 0.5


def test_current_unit():
    s = Current("i", 0, "A", SensorKind.PV)
    assert s.unit == "A"
    assert s.size_ == 2


# --- Frequency ---


def test_frequency():
    assert Frequency("f", 0, "Hz", SensorKind.AC).read(rd("1389")) == 50.01


def test_frequency_unit():
    s = Frequency("f", 0, "Hz", SensorKind.AC)
    assert s.unit == "Hz"
    assert s.size_ == 2


# --- PowerS (2-byte signed) ---


def test_powers_signed():
    assert PowerS("p", 0, "W", SensorKind.PV).read(rd("ffff")) == -1


def test_powers_unit():
    s = PowerS("p", 0, "W", SensorKind.PV)
    assert s.unit == "W"
    assert s.size_ == 2


# --- Power4 (4-byte unsigned) ---


def test_power4():
    assert Power4("p", 0, "W", SensorKind.AC).read(rd("0000005b")) == 91


def test_power4_sentinel_none():
    # 0xffffffff is undef => None
    assert Power4("p", 0, "W", SensorKind.AC).read(rd("ffffffff")) is None


def test_power4_unit():
    s = Power4("p", 0, "W", SensorKind.AC)
    assert s.unit == "W"
    assert s.size_ == 4


# --- Power4S (4-byte signed) ---


def test_power4s_negative():
    # 0xffffffff signed = -1
    assert Power4S("p", 0, "W", SensorKind.AC).read(rd("ffffffff")) == -1


def test_power4s_positive():
    assert Power4S("p", 0, "W", SensorKind.AC).read(rd("0000005b")) == 91


# --- Apparent4 (4-byte signed, VA) ---


def test_apparent4_reads_4_bytes():
    assert Apparent4("a", 0, "VA", SensorKind.AC).read(rd("0000005b")) == 91


def test_apparent4_size():
    assert Apparent4("a", 0, "VA", SensorKind.AC).size_ == 4


def test_apparent4_unit():
    assert Apparent4("a", 0, "VA", SensorKind.AC).unit == "VA"


# --- Reactive4 (4-byte signed, var) ---


def test_reactive4_reads_4_bytes():
    assert Reactive4("r", 0, "var", SensorKind.AC).read(rd("00000064")) == 100


def test_reactive4_unit():
    from goodwe_dt_lib.sensors import Reactive4

    assert Reactive4("r", 0, "var", SensorKind.AC).unit == "var"
    assert Reactive4("r", 0, "var", SensorKind.AC).size_ == 4


# --- Temp ---


def test_temp():
    assert Temp("t", 0, "T").read(rd("015e")) == 35.0


def test_temp_none():
    assert Temp("t", 0, "T").read(rd("ffff")) is None


def test_temp_minus1_none():
    # -1 (0xffff as signed = -1) also returns None
    assert Temp("t", 0, "T").read(rd("ffff")) is None


def test_temp_32767_none():
    # 32767 = 0x7fff sentinel
    assert Temp("t", 0, "T").read(rd("7fff")) is None


def test_temp_unit():
    s = Temp("t", 0, "T")
    assert s.unit == "C"
    assert s.size_ == 2


# --- Energy (2-byte, /10) ---


def test_energy_div10():
    assert Energy("e", 0, "kWh", SensorKind.PV).read(rd("0001")) == 0.1


def test_energy_sentinel_none():
    assert Energy("e", 0, "kWh", SensorKind.PV).read(rd("ffff")) is None


def test_energy_unit():
    s = Energy("e", 0, "kWh", SensorKind.PV)
    assert s.unit == "kWh"
    assert s.size_ == 2


# --- Energy4 (4-byte, /10) ---


def test_energy4_div10():
    assert Energy4("e", 0, "kWh", SensorKind.PV).read(rd("000076bd")) == 3039.7


def test_energy4_sentinel_none():
    assert Energy4("e", 0, "kWh", SensorKind.PV).read(rd("ffffffff")) is None


def test_energy4_unit():
    s = Energy4("e", 0, "kWh", SensorKind.PV)
    assert s.unit == "kWh"
    assert s.size_ == 4


# --- Energy4W (4-byte, /1000) ---


def test_energy4w_div1000():
    assert Energy4W("e", 0, "kWh", SensorKind.GRID).read(rd("000003e8")) == 1.0


def test_energy4w_sentinel_none():
    assert Energy4W("e", 0, "kWh", SensorKind.GRID).read(rd("ffffffff")) is None


def test_energy4w_unit():
    s = Energy4W("e", 0, "kWh", SensorKind.GRID)
    assert s.unit == "kWh"
    assert s.size_ == 4


# --- Integer ---


def test_integer_sentinel_zero():
    assert Integer("x", 0, "").read(rd("ffff")) == 0


def test_integer_normal():
    assert Integer("x", 0, "").read(rd("0042")) == 66


def test_integer_unit():
    s = Integer("x", 0, "name", unit="mode")
    assert s.unit == "mode"
    assert s.size_ == 2


# --- Long ---


def test_long():
    assert Long("h", 0, "", "h").read(rd("00001903")) == 6403


def test_long_sentinel_zero():
    assert Long("h", 0, "", "h").read(rd("ffffffff")) == 0


def test_long_unit():
    s = Long("h", 0, "h", "hours")
    assert s.size_ == 4


# --- Decimal ---


def test_decimal_pf():
    assert Decimal("pf", 0, 1000, "PF").read(rd("03e5")) == 0.997


def test_decimal_unit_default():
    s = Decimal("d", 0, 10, "name")
    assert s.unit == ""


def test_decimal_unit_custom():
    s = Decimal("d", 0, 10, "name", unit="W")
    assert s.unit == "W"


# --- Timestamp ---


def test_timestamp():
    assert str(Timestamp("ts", 0, "ts").read(rd("1a0616082b0e"))) == "2026-06-22 08:43:14"


def test_timestamp_unit():
    s = Timestamp("ts", 0, "ts")
    assert s.unit == ""
    assert s.size_ == 6


# --- Enum2 ---


def test_enum2():
    assert Enum2("wm", 0, {1: "Normal"}, "Work Mode").read(rd("0001")) == "Normal"


def test_enum2_unknown_key():
    assert Enum2("wm", 0, {1: "Normal"}, "Work Mode").read(rd("0002")) is None


def test_enum2_stores_labels():
    s = Enum2("wm", 0, {1: "Normal"}, "Work Mode")
    assert s._labels == {1: "Normal"}


# --- EnumBitmap4 ---


def test_enumbitmap4_empty():
    assert EnumBitmap4("dm", 0, {0: "A", 1: "B"}, "Derating").read(rd("ffffffff")) == ""


def test_enumbitmap4_single_bit():
    # value = 1 => bit 0 set => "A"
    assert EnumBitmap4("dm", 0, {0: "A", 1: "B"}, "Derating").read(rd("00000001")) == "A"


def test_enumbitmap4_two_bits():
    # value = 3 => bits 0 and 1 set => "A, B"
    assert EnumBitmap4("dm", 0, {0: "A", 1: "B"}, "Derating").read(rd("00000003")) == "A, B"


def test_enumbitmap4_stores_labels():
    s = EnumBitmap4("dm", 0, {0: "A"}, "Derating")
    assert s._labels == {0: "A"}


# --- SensorKind ---


def test_sensor_kind_values():
    assert SensorKind.PV.value == 1
    assert SensorKind.AC.value == 2
    assert SensorKind.UPS.value == 3
    assert SensorKind.BAT.value == 4
    assert SensorKind.GRID.value == 5
    assert SensorKind.BMS.value == 6


# --- Calculated ---


def test_calculated_compute():
    from goodwe_dt_lib.sensors import Calculated

    s = Calculated("calc", lambda d: d["a"] + d["b"], "Sum", "W")
    assert s.compute({"a": 3, "b": 4}) == 7


def test_calculated_no_offset():
    from goodwe_dt_lib.sensors import Calculated

    s = Calculated("calc", lambda d: 42, "Answer", "")
    assert s.offset == 0
    assert s.size_ == 0


def test_calculated_read_calls_getter():
    from goodwe_dt_lib.sensors import Calculated

    # read() with a dict (as A4/A6 will use)
    s = Calculated("calc", lambda d: 99, "X", "W")
    assert s.read({}) == 99
