"""
DT inverter register table — 51 sensors across runtime block, meter block,
and calculated (virtual) sensors.

Byte offsets are absolute positions within each block payload as documented in
docs/dt-register-map.md.  Use the RUNTIME_CMD / METER_CMD constants from
const.py to fetch the corresponding payloads.
"""

from .const import (
    WORK_MODES,
    SAFETY_COUNTRIES,
    DERATING_MODE_CODES,
    METER_COMMUNICATION_STATUS,
)
from .sensors import (
    Apparent4,
    Calculated,
    Current,
    Decimal,
    Energy,
    Energy4,
    Energy4W,
    Enum2,
    EnumBitmap4,
    Frequency,
    Integer,
    Long,
    Power4,
    Power4S,
    PowerS,
    Reactive4,
    SensorKind,
    Temp,
    Timestamp,
    Voltage,
)

# ---------------------------------------------------------------------------
# Runtime block sensors — payload 146 B, base reg 0x7594 (30100)
# boff = (register - 30100) * 2
# ---------------------------------------------------------------------------

RUNTIME_SENSORS: tuple = (
    Timestamp("timestamp", 0, "Timestamp"),
    Voltage("vpv1", 6, "PV1 Voltage", SensorKind.PV),
    Current("ipv1", 8, "PV1 Current", SensorKind.PV),
    Voltage("vpv2", 10, "PV2 Voltage", SensorKind.PV),
    Current("ipv2", 12, "PV2 Current", SensorKind.PV),
    Voltage("vline1", 30, "On-grid L1-L2 Voltage", SensorKind.AC),
    Voltage("vline2", 32, "On-grid L2-L3 Voltage", SensorKind.AC),
    Voltage("vline3", 34, "On-grid L3-L1 Voltage", SensorKind.AC),
    Voltage("vgrid1", 36, "On-grid L1 Voltage", SensorKind.AC),
    Voltage("vgrid2", 38, "On-grid L2 Voltage", SensorKind.AC),
    Voltage("vgrid3", 40, "On-grid L3 Voltage", SensorKind.AC),
    Current("igrid1", 42, "On-grid L1 Current", SensorKind.AC),
    Current("igrid2", 44, "On-grid L2 Current", SensorKind.AC),
    Current("igrid3", 46, "On-grid L3 Current", SensorKind.AC),
    Frequency("fgrid1", 48, "On-grid L1 Frequency", SensorKind.AC),
    Frequency("fgrid2", 50, "On-grid L2 Frequency", SensorKind.AC),
    Frequency("fgrid3", 52, "On-grid L3 Frequency", SensorKind.AC),
    Power4("total_inverter_power", 54, "Total Inverter Power", SensorKind.AC),
    Integer("work_mode", 58, "Work Mode"),
    Enum2("work_mode_label", 58, WORK_MODES, "Work Mode Label"),
    Long("error_codes", 60, "Error Codes"),
    Integer("warning_code", 64, "Warning Code"),
    Apparent4("apparent_power", 66, "Apparent Power", SensorKind.AC),
    Reactive4("reactive_power", 70, "Reactive Power", SensorKind.AC),
    PowerS("total_input_power", 74, "Total Input Power", SensorKind.PV),
    Decimal("power_factor", 78, 1000, "Power Factor", kind=SensorKind.GRID),
    Temp("temperature", 82, "Temperature", SensorKind.AC),
    Temp("temperature_heatsink", 84, "Heatsink Temperature", SensorKind.AC),
    Energy("e_day", 88, "Today's PV Generation", SensorKind.PV),
    Energy4("e_total", 90, "Total PV Generation", SensorKind.PV),
    Long("h_total", 94, "Total Running Hours", unit="h", kind=SensorKind.PV),
    Integer("safety_country", 98, "Safety Country Code", kind=SensorKind.AC),
    Enum2("safety_country_label", 98, SAFETY_COUNTRIES, "Safety Country", SensorKind.AC),
    Integer("funbit", 124, "Function Bit", kind=SensorKind.PV),
    Voltage("vbus", 126, "Bus Voltage", SensorKind.PV),
    Voltage("vnbus", 128, "N-Bus Voltage", SensorKind.PV),
    Long("derating_mode", 130, "Derating Mode"),
    EnumBitmap4("derating_mode_label", 130, DERATING_MODE_CODES, "Derating Mode Label"),
    Integer("rssi", 144, "RSSI"),
)

# ---------------------------------------------------------------------------
# Meter block sensors — payload 30 B, base reg 0x75f3 (30195)
# boff = (register - 30195) * 2
# ---------------------------------------------------------------------------

METER_SENSORS: tuple = (
    Power4S("meter_active_power", 0, "Meter Active Power", SensorKind.GRID),
    Energy4W("meter_e_total_exp", 4, "Meter Total Export Energy", SensorKind.GRID),
    Energy4W("meter_e_total_imp", 8, "Meter Total Import Energy", SensorKind.GRID),
    Integer("meter_comm_status", 28, "Meter Communication Status"),
    Enum2("meter_comm_label", 28, METER_COMMUNICATION_STATUS, "Meter Communication Label"),
)

# ---------------------------------------------------------------------------
# Calculated (virtual) sensors — derived from decoded runtime+meter values
# ---------------------------------------------------------------------------

CALCULATED_SENSORS: tuple = (
    Calculated("ppv1", lambda d: round(d["vpv1"] * d["ipv1"]), "PV1 Power", "W", SensorKind.PV),
    Calculated("ppv2", lambda d: round(d["vpv2"] * d["ipv2"]), "PV2 Power", "W", SensorKind.PV),
    Calculated(
        "ppv",
        lambda d: round(d["vpv1"] * d["ipv1"]) + round(d["vpv2"] * d["ipv2"]),
        "PV Power",
        "W",
        SensorKind.PV,
    ),
    Calculated(
        "pgrid1",
        lambda d: round(d["vgrid1"] * d["igrid1"]),
        "On-grid L1 Power",
        "W",
        SensorKind.AC,
    ),
    Calculated(
        "pgrid2",
        lambda d: round(d["vgrid2"] * d["igrid2"]),
        "On-grid L2 Power",
        "W",
        SensorKind.AC,
    ),
    Calculated(
        "pgrid3",
        lambda d: round(d["vgrid3"] * d["igrid3"]),
        "On-grid L3 Power",
        "W",
        SensorKind.AC,
    ),
    Calculated(
        "house_consumption",
        lambda d: abs(d.get("ppv", 0) - d.get("meter_active_power", 0)),
        "House Consumption",
        "W",
        SensorKind.AC,
    ),
)
