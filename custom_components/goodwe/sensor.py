"""Sensor platform for the GoodWe DT integration.

Entity ``unique_id``s are ``f"{DOMAIN}-{sensor.id_}-{serial_number}"`` — identical to
the previous integration — so dashboards, history and automations carry over.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import GoodweConfigEntry, GoodweUpdateCoordinator
from .goodwe_dt_lib import DtInverter
from .goodwe_dt_lib.sensors import EnumBitmap4, Enum2, Sensor, SensorKind

_LOGGER = logging.getLogger(__name__)

# Sensors reset to 0 at local midnight. A DT inverter is solar-only and sleeps at
# night, so it cannot zero these itself when the day rolls over — HA does it.
DAILY_RESET = ["e_day"]

# Primary (non-diagnostic) sensors.
_MAIN_SENSORS = (
    "ppv",
    "house_consumption",
    "e_day",
    "e_total",
    "meter_e_total_exp",
    "meter_e_total_imp",
)

_ICONS: dict[SensorKind, str] = {
    SensorKind.PV: "mdi:solar-power",
    SensorKind.AC: "mdi:power-plug-outline",
    SensorKind.UPS: "mdi:power-plug-off-outline",
    SensorKind.BAT: "mdi:battery-high",
    SensorKind.GRID: "mdi:transmission-tower",
}


@dataclass(frozen=True)
class GoodweSensorEntityDescription(SensorEntityDescription):
    """Describes a GoodWe sensor entity."""

    value: Callable[[GoodweUpdateCoordinator, str], Any] = (
        lambda coordinator, sensor: coordinator.sensor_value(sensor)
    )
    available: Callable[[GoodweUpdateCoordinator], bool] = (
        lambda coordinator: coordinator.last_update_success
    )


_DESCRIPTIONS: dict[str, GoodweSensorEntityDescription] = {
    "A": GoodweSensorEntityDescription(
        key="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    "V": GoodweSensorEntityDescription(
        key="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    "W": GoodweSensorEntityDescription(
        key="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    "kWh": GoodweSensorEntityDescription(
        key="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda coordinator, sensor: coordinator.total_sensor_value(sensor),
        available=lambda coordinator: coordinator.data is not None,
    ),
    "VA": GoodweSensorEntityDescription(
        key="VA",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        entity_registry_enabled_default=False,
    ),
    "var": GoodweSensorEntityDescription(
        key="var",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
    ),
    "C": GoodweSensorEntityDescription(
        key="C",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "Hz": GoodweSensorEntityDescription(
        key="Hz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    "h": GoodweSensorEntityDescription(
        key="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_registry_enabled_default=False,
    ),
}
DIAG_SENSOR = GoodweSensorEntityDescription(
    key="_",
    state_class=SensorStateClass.MEASUREMENT,
)
TEXT_SENSOR = GoodweSensorEntityDescription(key="text")
ENUM_SENSOR = GoodweSensorEntityDescription(key="enum", device_class=SensorDeviceClass.ENUM)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GoodweConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the GoodWe DT sensors from a config entry."""
    inverter = config_entry.runtime_data.inverter
    coordinator = config_entry.runtime_data.coordinator
    device_info = config_entry.runtime_data.device_info

    async_add_entities(
        InverterSensor(coordinator, device_info, inverter, sensor)
        for sensor in inverter.sensors()
    )

    async_add_entities(
        [GoodweExportEnabledSensor(coordinator, device_info, inverter.serial_number)]
    )


class InverterSensor(CoordinatorEntity[GoodweUpdateCoordinator], SensorEntity):
    """A single GoodWe DT inverter sensor."""

    _attr_has_entity_name = True
    entity_description: GoodweSensorEntityDescription

    def __init__(
        self,
        coordinator: GoodweUpdateCoordinator,
        device_info: DeviceInfo,
        inverter: DtInverter,
        sensor: Sensor,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = sensor.name.strip()
        self._attr_unique_id = f"{DOMAIN}-{sensor.id_}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_entity_category = (
            EntityCategory.DIAGNOSTIC if sensor.id_ not in _MAIN_SENSORS else None
        )
        if sensor.unit in _DESCRIPTIONS:
            self.entity_description = _DESCRIPTIONS[sensor.unit]
        elif isinstance(sensor, Enum2):
            self.entity_description = ENUM_SENSOR
            self._attr_options = list(sensor._labels.values())
        elif isinstance(sensor, EnumBitmap4) or sensor.id_ == "timestamp":
            self.entity_description = TEXT_SENSOR
        else:
            self.entity_description = DIAG_SENSOR
            self._attr_native_unit_of_measurement = sensor.unit or None
        self._attr_icon = _ICONS.get(sensor.kind) if sensor.kind else None
        self._sensor = sensor
        self._stop_reset: Callable[[], None] | None = None

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the sensor value."""
        return self.entity_description.value(self.coordinator, self._sensor.id_)

    @property
    def available(self) -> bool:
        """Return whether the entity is available.

        Delegated to the description: 'daily'/'total' energy sensors stay available
        (showing the last known value) even while the inverter sleeps at night.
        """
        return self.entity_description.available(self.coordinator)

    @callback
    def async_reset(self, now) -> None:
        """Reset a daily sensor to 0 at local midnight (inverter is asleep then)."""
        if self.coordinator.is_asleep:
            self.coordinator.reset_sensor(self._sensor.id_)
            self.async_write_ha_state()
            _LOGGER.debug("GoodWe reset %s to 0", self.name)
        next_midnight = dt_util.start_of_local_day(
            dt_util.now() + timedelta(days=1, minutes=1)
        )
        self._stop_reset = async_track_point_in_time(
            self.hass, self.async_reset, next_midnight
        )

    async def async_added_to_hass(self) -> None:
        """Schedule the midnight reset for daily sensors."""
        if self._sensor.id_ in DAILY_RESET:
            next_midnight = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))
            self._stop_reset = async_track_point_in_time(
                self.hass, self.async_reset, next_midnight
            )
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the midnight reset."""
        if self._sensor.id_ in DAILY_RESET and self._stop_reset is not None:
            self._stop_reset()
        await super().async_will_remove_from_hass()


class GoodweExportEnabledSensor(CoordinatorEntity[GoodweUpdateCoordinator], SensorEntity):
    """Read-only diagnostic: is the grid export limit active."""

    _attr_has_entity_name = True
    _attr_name = "Grid export enabled"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["off", "on"]

    def __init__(self, coordinator, device_info, serial_number) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}-grid_export_enabled-{serial_number}"
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.settings_value("grid_export_enabled") is not None
        )

    @property
    def native_value(self) -> str | None:
        val = self.coordinator.settings_value("grid_export_enabled")
        return None if val is None else ("on" if val else "off")
