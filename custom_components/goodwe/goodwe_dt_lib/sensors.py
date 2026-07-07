"""
Sensor type system and byte decoders for the GoodWe DT inverter library.

Each Sensor subclass knows how to decode its value from a raw payload via a
ProtocolResponse.  Byte offsets are absolute positions within the block payload
(runtime or meter) — A4 supplies the concrete offsets when building sensor lists.
"""

import enum
import io
from datetime import datetime


# ---------------------------------------------------------------------------
# ProtocolResponse — thin wrapper around a bytes buffer with seek/read
# ---------------------------------------------------------------------------


class ProtocolResponse:
    def __init__(self, payload: bytes) -> None:
        self._b = io.BytesIO(payload)

    def seek(self, byte_offset: int) -> None:
        self._b.seek(byte_offset)

    def read(self, size: int) -> bytes:
        return self._b.read(size)


# ---------------------------------------------------------------------------
# SensorKind
# ---------------------------------------------------------------------------


class SensorKind(enum.Enum):
    PV = 1
    AC = 2
    UPS = 3
    BAT = 4
    GRID = 5
    BMS = 6


# ---------------------------------------------------------------------------
# Low-level decode helpers (read from current stream position; big-endian)
# ---------------------------------------------------------------------------


def read_bytes2(d: ProtocolResponse, undef=None):
    v = int.from_bytes(d.read(2), "big", signed=False)
    return undef if v == 0xFFFF else v


def read_bytes2_signed(d: ProtocolResponse) -> int:
    return int.from_bytes(d.read(2), "big", signed=True)


def read_bytes4(d: ProtocolResponse, undef=None):
    v = int.from_bytes(d.read(4), "big", signed=False)
    return undef if v == 0xFFFFFFFF else v


def read_bytes4_signed(d: ProtocolResponse) -> int:
    return int.from_bytes(d.read(4), "big", signed=True)


def read_voltage(d: ProtocolResponse) -> float:
    v = int.from_bytes(d.read(2), "big")
    return float(v) / 10 if v != 0xFFFF else 0


def read_current(d: ProtocolResponse) -> float:
    v = int.from_bytes(d.read(2), "big")
    return float(v) / 10 if v != 0xFFFF else 0


def read_freq(d: ProtocolResponse) -> float:
    v = int.from_bytes(d.read(2), "big", signed=True)
    return float(v) / 100


def read_temp(d: ProtocolResponse):
    v = int.from_bytes(d.read(2), "big", signed=True)
    return None if v in (-1, 32767) else float(v) / 10


def read_decimal2(d: ProtocolResponse, scale) -> float:
    return float(int.from_bytes(d.read(2), "big", signed=True)) / scale


def read_datetime(d: ProtocolResponse) -> datetime:
    b = d.read(6)
    return datetime(2000 + b[0], b[1], b[2], b[3], b[4], b[5])


def decode_bitmap(value: int, labels: dict) -> str:
    out = []
    bits = value
    for i in range(32):
        if bits & 1 and labels.get(i):
            out.append(labels[i])
        bits >>= 1
    return ", ".join(out)


# ---------------------------------------------------------------------------
# Sensor base class
# ---------------------------------------------------------------------------


class Sensor:
    def __init__(self, id_, offset, name, size_, unit, kind=None) -> None:
        self.id_ = id_
        self.offset = offset
        self.name = name
        self.size_ = size_
        self.unit = unit
        self.kind = kind

    def read_value(self, data: ProtocolResponse):
        raise NotImplementedError

    def read(self, data: ProtocolResponse):
        data.seek(self.offset)
        return self.read_value(data)


# ---------------------------------------------------------------------------
# Typed sensor subclasses
# ---------------------------------------------------------------------------


class Voltage(Sensor):
    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=2, unit="V", kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_voltage(data)


class Current(Sensor):
    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=2, unit="A", kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_current(data)


class Frequency(Sensor):
    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=2, unit="Hz", kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_freq(data)


class PowerS(Sensor):
    """2-byte signed power (W)."""

    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=2, unit="W", kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_bytes2_signed(data)


class Power4(Sensor):
    """4-byte unsigned power (W); 0xffffffff → None."""

    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=4, unit="W", kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_bytes4(data, undef=None)


class Power4S(Sensor):
    """4-byte signed power (W)."""

    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=4, unit="W", kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_bytes4_signed(data)


class Apparent4(Sensor):
    """4-byte signed apparent power (VA).  size_=4 fixes upstream size_=2 quirk."""

    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=4, unit="VA", kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_bytes4_signed(data)


class Reactive4(Sensor):
    """4-byte signed reactive power (var).  size_=4 fixes upstream size_=2 quirk."""

    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=4, unit="var", kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_bytes4_signed(data)


class Energy(Sensor):
    """2-byte unsigned energy counter (kWh, /10); 0xffff → None."""

    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=2, unit="kWh", kind=kind)

    def read_value(self, data: ProtocolResponse):
        v = read_bytes2(data)
        return v / 10 if v is not None else None


class Energy4(Sensor):
    """4-byte unsigned energy counter (kWh, /10); 0xffffffff → None."""

    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=4, unit="kWh", kind=kind)

    def read_value(self, data: ProtocolResponse):
        v = read_bytes4(data)
        return v / 10 if v is not None else None


class Energy4W(Sensor):
    """4-byte unsigned energy counter in Wh (kWh, /1000); 0xffffffff → None."""

    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=4, unit="kWh", kind=kind)

    def read_value(self, data: ProtocolResponse):
        v = read_bytes4(data)
        return v / 1000 if v is not None else None


class Temp(Sensor):
    """2-byte signed temperature (°C, /10); -1 or 32767 → None."""

    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=2, unit="C", kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_temp(data)


class Decimal(Sensor):
    """2-byte signed integer divided by scale."""

    def __init__(self, id_, offset, scale, name, unit="", kind=None) -> None:
        super().__init__(id_, offset, name, size_=2, unit=unit, kind=kind)
        self._scale = scale

    def read_value(self, data: ProtocolResponse):
        return read_decimal2(data, self._scale)


class Integer(Sensor):
    """2-byte unsigned integer; 0xffff → 0 (undef treated as zero)."""

    def __init__(self, id_, offset, name, unit="", kind=None) -> None:
        super().__init__(id_, offset, name, size_=2, unit=unit, kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_bytes2(data, undef=0)


class Long(Sensor):
    """4-byte unsigned integer; 0xffffffff → 0."""

    def __init__(self, id_, offset, name, unit="", kind=None) -> None:
        super().__init__(id_, offset, name, size_=4, unit=unit, kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_bytes4(data, undef=0)


class Timestamp(Sensor):
    """6-byte packed datetime (YY MM DD HH MM SS, year offset 2000)."""

    def __init__(self, id_, offset, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=6, unit="", kind=kind)

    def read_value(self, data: ProtocolResponse):
        return read_datetime(data)


class Enum2(Sensor):
    """2-byte unsigned integer mapped to a string label via a dict."""

    def __init__(self, id_, offset, labels: dict, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=2, unit="", kind=kind)
        self._labels = labels

    def read_value(self, data: ProtocolResponse):
        return self._labels.get(read_bytes2(data, undef=0))


class EnumBitmap4(Sensor):
    """4-byte unsigned bitmap decoded to a comma-separated label string."""

    def __init__(self, id_, offset, labels: dict, name, kind=None) -> None:
        super().__init__(id_, offset, name, size_=4, unit="", kind=kind)
        self._labels = labels

    def read_value(self, data: ProtocolResponse):
        return decode_bitmap(read_bytes4(data, undef=0), self._labels)


class Calculated(Sensor):
    """
    Virtual sensor whose value is derived from already-decoded sensor values.

    The getter callable receives the decoded dict and returns the computed value.
    A4/A6 call ``compute(decoded_dict)`` after decoding the raw sensors.
    ``read(data)`` is also supported (passes data directly to getter) for
    compatibility with generic read loops.
    """

    def __init__(self, id_, getter, name, unit, kind=None) -> None:
        super().__init__(id_, offset=0, name=name, size_=0, unit=unit, kind=kind)
        self._getter = getter

    def read_value(self, data):
        return self._getter(data)

    def read(self, data):  # type: ignore[override]
        # No seek — data may be a dict or a ProtocolResponse; delegate directly.
        return self._getter(data)

    def compute(self, decoded: dict):
        return self._getter(decoded)
