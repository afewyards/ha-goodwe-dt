# DT register map — authoritative reverse-engineering reference

Verified against live unit **GW3000-DNS-30**, S/N `xxxxxxxxxxxxxx`, FW `4.5.0b`,
on 2026-06-22 (UDP/8899). Raw response bytes decode to the listed values; this table is
the source of truth for the re-derived decoder. Re-verify any row against `goodwe` baseline
before trusting it (zero-diff gate).

## Transport & framing

- **Transport:** Modbus-RTU over **UDP**, port **8899**. Inverter Modbus address `0x7f`.
- **Request (raw Modbus-RTU, no prefix):** `7f 03 <reg_hi reg_lo> <cnt_hi cnt_lo> <crc_lo crc_hi>`
  - func `0x03` = read holding registers. CRC = Modbus CRC16 (poly 0xA001), **little-endian** appended.
  - Runtime: `7f 03 75 94 00 49 <crc>` → 73 regs @ `0x7594` (30100).
  - Meter:   `7f 03 75 f3 00 0f <crc>` → 15 regs @ `0x75f3` (30195).
- **Response (AA55-wrapped):** `aa 55 7f 03 <bytecount:1> <payload> <crc_lo crc_hi>`
  - Header is 5 bytes (`aa55`, addr, func, bytecount); payload = `bytecount` bytes; then CRC16
    **little-endian** (same byte order as the request), computed over `addr func bytecount payload`
    (the `aa55` header is excluded).
  - Runtime payload = 146 bytes (73 regs). Meter payload = 30 bytes (15 regs).
- **Register → payload byte offset:** `boff = (register - block_base) * 2`,
  where `block_base` = 30100 (runtime) or 30195 (meter).

## Decode-type rules (only the 20 types this model uses)

| Type | read width | signed | transform | "no value" sentinel |
|------|-----------:|--------|-----------|---------------------|
| `Timestamp` | 6 | — | `datetime(2000+B0,B1,B2,B3,B4,B5)` | — |
| `Voltage` | 2 | unsigned | `/10` | `0xffff` → `0` |
| `Current` | 2 | unsigned | `/10` | `0xffff` → `0` |
| `CurrentSmA` | 2 | **signed** | `/10` (unit mA) | none |
| `Frequency` | 2 | **signed** | `/100` | none |
| `PowerS` | 2 | **signed** | `×1` | none |
| `Power4` | 4 | unsigned | `×1` | `0xffffffff` → `None` |
| `Power4S` | 4 | **signed** | `×1` | none |
| `Apparent4` | **4** ⚠ | **signed** | `×1` | none |
| `Reactive4` | **4** ⚠ | **signed** | `×1` | none |
| `Energy` | 2 | unsigned | `/10` | `0xffff` → `None` |
| `Energy4` | 4 | unsigned | `/10` | `0xffffffff` → `None` |
| `Energy4W` | 4 | unsigned | `/1000` | `0xffffffff` → `None` |
| `Temp` | 2 | **signed** | `/10` | `-1` or `32767` → `None` |
| `Decimal` | 2 | **signed** | `/scale` (power_factor scale=1000) | none |
| `Integer` | 2 | unsigned | `×1` | `0xffff` → `0` (undef=0) |
| `Long` | 4 | unsigned | `×1` | `0xffffffff` → `0` (undef=0) |
| `Enum2` | 2 | unsigned | `labels.get(value)` — mapped label (may itself be `""`) | key absent from map → `None` |
| `EnumBitmap4` | 4 | unsigned | per-bit label join (`decode_bitmap`) | — |
| `Calculated` | 0 | — | formula over other sensors (see below) | — |

⚠ **`Apparent4`/`Reactive4` declare `size_=2` in the baseline but `read_value` reads 4
signed bytes.** Field spacing (30133→30135→30137) confirms 4-byte fields. Decode 4 bytes.

## Runtime block — `0x7594` (30100), payload 146 B

| boff | reg | id | type | unit | kind |
|----:|----:|----|------|------|------|
| 0 | 30100 | `timestamp` | Timestamp | | |
| 6 | 30103 | `vpv1` | Voltage | V | PV |
| 8 | 30104 | `ipv1` | Current | A | PV |
| 10 | 30105 | `vpv2` | Voltage | V | PV |
| 12 | 30106 | `ipv2` | Current | A | PV |
| 30 | 30115 | `vline1` | Voltage | V | AC |
| 32 | 30116 | `vline2` | Voltage | V | AC |
| 34 | 30117 | `vline3` | Voltage | V | AC |
| 36 | 30118 | `vgrid1` | Voltage | V | AC |
| 38 | 30119 | `vgrid2` | Voltage | V | AC |
| 40 | 30120 | `vgrid3` | Voltage | V | AC |
| 42 | 30121 | `igrid1` | Current | A | AC |
| 44 | 30122 | `igrid2` | Current | A | AC |
| 46 | 30123 | `igrid3` | Current | A | AC |
| 48 | 30124 | `fgrid1` | Frequency | Hz | AC |
| 50 | 30125 | `fgrid2` | Frequency | Hz | AC |
| 52 | 30126 | `fgrid3` | Frequency | Hz | AC |
| 54 | 30127 | `total_inverter_power` | Power4 | W | AC |
| 58 | 30129 | `work_mode` | Integer | | |
| 58 | 30129 | `work_mode_label` | Enum2 (`WORK_MODES_DT`) | | |
| 60 | 30130 | `error_codes` | Long | | |
| 64 | 30132 | `warning_code` | Integer | | |
| 66 | 30133 | `apparent_power` | Apparent4 (4B) | VA | AC |
| 70 | 30135 | `reactive_power` | Reactive4 (4B) | var | AC |
| 74 | 30137 | `total_input_power` | PowerS | W | PV |
| 78 | 30139 | `power_factor` | Decimal(scale=1000) | | GRID |
| 82 | 30141 | `temperature` | Temp | C | AC |
| 84 | 30142 | `temperature_heatsink` | Temp | C | AC |
| 88 | 30144 | `e_day` | Energy | kWh | PV |
| 90 | 30145 | `e_total` | Energy4 | kWh | PV |
| 94 | 30147 | `h_total` | Long | h | PV |
| 98 | 30149 | `safety_country` | Integer | | AC |
| 98 | 30149 | `safety_country_label` | Enum2 (`SAFETY_COUNTRIES_DT`) | | AC |
| 124 | 30162 | `funbit` | Integer | | PV |
| 126 | 30163 | `vbus` | Voltage | V | PV |
| 128 | 30164 | `vnbus` | Voltage | V | PV |
| 130 | 30165 | `derating_mode` | Long | | |
| 130 | 30165 | `derating_mode_label` | EnumBitmap4 | | |
| 144 | 30172 | `rssi` | Integer | | |

Unread gaps for this model: boff 14–29 (regs 30107–30114: vpv3/4, ipv3/4 — absent on 2-MPPT
D-NS), 76–77, 80–81, 86–87, 100–123, 134–143.

## Meter block — `0x75f3` (30195), payload 30 B

| boff | reg | id | type | unit | kind |
|----:|----:|----|------|------|------|
| 0 | 30195 | `meter_active_power` | Power4S | W | GRID |
| 4 | 30197 | `meter_e_total_exp` | Energy4W | kWh | GRID |
| 8 | 30199 | `meter_e_total_imp` | Energy4W | kWh | GRID |
| 28 | 30209 | `meter_comm_status` | Integer | | |
| 28 | 30209 | `meter_comm_label` | Enum2 (`METER_COMMUNICATION_STATUS`) | | |
| ~~30~~ | ~~30210~~ | ~~`leakage_current`~~ | **DROPPED** (decision 2026-06-22) | | |

## Calculated sensors (no own register)

| id | formula |
|----|---------|
| `ppv1` | `round(vpv1 * ipv1)` |
| `ppv2` | `round(vpv2 * ipv2)` |
| `ppv` | sum of present `ppvN` |
| `pgrid1` | `round(vgrid1 * igrid1)` (similarly pgrid2/3) |
| `house_consumption` | `abs(ppv - meter_active_power)` |

## Anomalies / gotchas (must handle in re-derivation)

1. **`Apparent4`/`Reactive4` read 4 bytes despite `size_=2`.** Decode 4 signed bytes.
2. **`leakage_current` @ 30210 is past the 15-register meter read** (covers 30195–30209,
   bytes 0–29). Baseline returns `0.0` from an out-of-bounds `BytesIO.read`.
   **Decision (2026-06-22): DROP the sensor** — not exposed. Result: **51 sensors** total.
   (Old integration's `leakage_current` entity always read `0.0`; it simply won't be
   recreated — harmless for drop-in.)
3. **`0xffff`/`0xffffffff` sentinels** mean "no value": Voltage/Current→`0`, Integer/Long→`0`
   (undef=0), Energy/Power4→`None`. Temp uses `-1`/`32767`→`None`. Replicate per-type.
4. **Signedness varies** — Frequency, Temp, PowerS, Power4S, Apparent4, Reactive4, Decimal,
   CurrentSmA are signed; Voltage/Current/Power/Energy/Integer/Long are unsigned.
5. **Two sensors share one register** (label + raw): `work_mode`/`work_mode_label`,
   `safety_country`/`safety_country_label`, `meter_comm_status`/`meter_comm_label`,
   `derating_mode`/`derating_mode_label`. Same offset, different type.
6. **Enum label maps** (`WORK_MODES_DT`, `SAFETY_COUNTRIES_DT`, `METER_COMMUNICATION_STATUS`,
   derating bitmap) must be copied verbatim from baseline `const.py` so `sensor.py` renders
   identical ENUM options/`unique_id` parity.

## Verification status

Sensor count: **51** (52 decoded by baseline minus dropped `leakage_current`).
All non-calculated runtime sensors decoded correctly from captured bytes (spot-checked:
`vpv1`=133.2 V from `0x0534`, `timestamp` from `1a 06 16 08 2b 0e`, `e_total`=3039.7 kWh
from `0x000076bd`). Pending captures: night/asleep state, meter-with-load, low-sun edge.
