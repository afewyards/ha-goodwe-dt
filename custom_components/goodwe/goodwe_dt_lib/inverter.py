"""DtInverter — ties together transport, decoders and register table."""

from __future__ import annotations

from . import settings as _settings
from .const import DEVICE_INFO_CMD, METER_CMD, MODBUS_ADDR, MODEL_CMD, RUNTIME_CMD
from .protocol import UdpTransport
from .registers import CALCULATED_SENSORS, METER_SENSORS, RUNTIME_SENSORS
from .sensors import ProtocolResponse


class DtInverter:
    def __init__(self, host: str, port: int = 8899, timeout: float = 1.0, retries: int = 3) -> None:
        self.transport = UdpTransport(host, port, MODBUS_ADDR, timeout, retries)
        self.serial_number: str | None = None
        self.model_name: str | None = None
        self.firmware: str | None = None
        self.arm_firmware: str | None = None

    @staticmethod
    def _decode_device_info(version_payload: bytes):
        """Return (serial, firmware, model_or_None) from the 40-reg device-version payload."""
        serial = version_payload[6:22].decode("ascii", "ignore").strip("\x00").strip()
        dsp1 = int.from_bytes(version_payload[66:68], "big")
        dsp2 = int.from_bytes(version_payload[68:70], "big")
        arm  = int.from_bytes(version_payload[70:72], "big")
        firmware = f"{dsp1}.{dsp2}.{arm:02x}"
        try:
            model = version_payload[22:32].decode("ascii").rstrip()
            if not model.isprintable() or not model.strip():
                model = None
        except (UnicodeDecodeError, ValueError):
            model = None
        return serial, firmware, model

    async def read_device_info(self) -> None:
        vp = await self.transport.send_command(*DEVICE_INFO_CMD)
        self.serial_number, self.firmware, self.model_name = self._decode_device_info(vp)
        if self.model_name is None:
            mp = await self.transport.send_command(*MODEL_CMD)
            self.model_name = mp[0:16].decode("ascii", "ignore").rstrip("\x00").strip()

    def _decode_runtime(self, runtime_payload: bytes, meter_payload: bytes) -> dict:
        data = {}
        rp = ProtocolResponse(runtime_payload)
        for s in RUNTIME_SENSORS:
            data[s.id_] = s.read(rp)
        mp = ProtocolResponse(meter_payload)
        for s in METER_SENSORS:
            data[s.id_] = s.read(mp)
        for s in CALCULATED_SENSORS:
            data[s.id_] = s.compute(data)
        return data

    async def read_runtime_data(self) -> dict:
        runtime = await self.transport.send_command(*RUNTIME_CMD)
        meter   = await self.transport.send_command(*METER_CMD)
        return self._decode_runtime(runtime, meter)

    async def wake(self) -> bool:
        return await self.transport.wake()

    async def read_settings(self) -> dict:
        limit = await self.transport.send_command(_settings.GRID_EXPORT_LIMIT_REG, 1)
        enabled = await self.transport.send_command(_settings.GRID_EXPORT_ENABLED_REG, 1)
        return {
            "grid_export_limit": int.from_bytes(limit[:2], "big"),
            "grid_export_enabled": int.from_bytes(enabled[:2], "big"),
        }

    async def set_grid_export_limit(self, pct: int) -> None:
        pct = max(_settings.EXPORT_LIMIT_MIN, min(_settings.EXPORT_LIMIT_MAX, int(pct)))
        await self.transport.write_register(_settings.GRID_EXPORT_LIMIT_REG, pct)

    def sensors(self) -> list:
        return list(RUNTIME_SENSORS) + list(METER_SENSORS) + list(CALCULATED_SENSORS)


async def connect(host: str, port: int = 8899, timeout: float = 1.0, retries: int = 3) -> DtInverter:
    inv = DtInverter(host, port, timeout, retries)
    await inv.read_device_info()
    return inv
