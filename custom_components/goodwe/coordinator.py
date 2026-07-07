"""Update coordinator for the GoodWe DT integration.

Wraps the pure :class:`RecoveryPolicy` (night/morning state machine) around the
vendored :class:`DtInverter`. On a streak of failed reads it slows the poll
cadence and sends the UDP wake probe before each retry, so the integration
recovers automatically when a DT inverter powers back up at dawn — without a
manual reload.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ASLEEP_AFTER,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    NIGHT_RECOVERY_INTERVAL,
)
from .goodwe_dt_lib import DtInverter
from .goodwe_dt_lib.exceptions import InverterError, RequestFailedException
from .goodwe_dt_lib.recovery import RecoveryPolicy

_LOGGER = logging.getLogger(__name__)

@dataclass
class GoodweRuntimeData:
    """Runtime data stored on the config entry."""

    inverter: DtInverter
    coordinator: "GoodweUpdateCoordinator"
    device_info: DeviceInfo


GoodweConfigEntry: TypeAlias = ConfigEntry[GoodweRuntimeData]


class GoodweUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch runtime data from a GoodWe DT inverter with night-sleep recovery."""

    config_entry: GoodweConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GoodweConfigEntry,
        inverter: DtInverter,
    ) -> None:
        """Initialize the update coordinator."""
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.inverter: DtInverter = inverter
        self._last_data: dict[str, Any] = {}
        self._settings: dict[str, Any] = {}
        self._policy = RecoveryPolicy(
            asleep_after=ASLEEP_AFTER,
            awake_interval=scan_interval,
            asleep_interval=NIGHT_RECOVERY_INTERVAL,
        )

    @property
    def is_asleep(self) -> bool:
        """True when the inverter is in the night-sleep recovery state."""
        return self._policy.should_wake

    def settings_value(self, sid: str) -> Any:
        """Return a cached settings value (or None if not yet read)."""
        return self._settings.get(sid)

    async def async_read_settings(self) -> None:
        """Best-effort refresh of the settings cache. Never raises."""
        try:
            self._settings = await self.inverter.read_settings()
        except Exception:  # noqa: BLE001 - settings are best-effort
            _LOGGER.debug("Settings read failed", exc_info=True)

    async def async_set_grid_export_limit(self, pct: int) -> None:
        """Write the export limit, confirm by read-back, and notify listeners."""
        await self.inverter.set_grid_export_limit(pct)
        await self.async_read_settings()
        self.async_update_listeners()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the inverter, handling night sleep and morning wake."""
        was_asleep = self._policy.should_wake
        # While asleep, the dongle does not answer until it receives a wake probe.
        if self._policy.should_wake:
            try:
                woke = await self.inverter.wake()
                _LOGGER.debug("Sent wake probe to inverter (reply=%s)", woke)
            except Exception:  # noqa: BLE001 - wake is best-effort, never fatal
                _LOGGER.debug("Wake probe failed", exc_info=True)

        try:
            self._last_data = self.data or {}
            data = await self.inverter.read_runtime_data()
        except RequestFailedException as ex:
            # UDP comms are unreliable by nature; tolerate isolated misses and only
            # report unavailable after a streak. Slow the cadence + arm the wake
            # probe once the streak crosses the threshold (inverter is asleep).
            self.update_interval = timedelta(
                seconds=self._policy.on_failure(ex.consecutive_failures_count)
            )
            if ex.consecutive_failures_count < ASLEEP_AFTER:
                _LOGGER.debug(
                    "No response received (streak of %d)",
                    ex.consecutive_failures_count,
                )
                return self._last_data
            _LOGGER.debug(
                "Inverter not responding (streak of %d) — recovery mode every %ds",
                ex.consecutive_failures_count,
                NIGHT_RECOVERY_INTERVAL,
            )
            raise UpdateFailed(ex) from ex
        except InverterError as ex:
            raise UpdateFailed(ex) from ex

        # Success — resume the normal daytime cadence.
        if was_asleep or not self._settings:
            await self.async_read_settings()
        self.update_interval = timedelta(seconds=self._policy.on_success())
        return data

    def sensor_value(self, sensor: str) -> Any:
        """Return the current (or last known) value of a sensor."""
        val = self.data.get(sensor) if self.data else None
        return val if val is not None else self._last_data.get(sensor)

    def total_sensor_value(self, sensor: str) -> Any:
        """Return the current value of a 'total' (never 0) sensor."""
        val = self.data.get(sensor) if self.data else None
        return val or self._last_data.get(sensor)

    def reset_sensor(self, sensor: str) -> None:
        """Reset a daily cumulative sensor to 0 (called at local midnight)."""
        self._last_data[sensor] = 0
        if self.data is not None:
            self.data[sensor] = 0
