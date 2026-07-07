"""Number platform for the GoodWe DT integration — writable grid export limit."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GoodweConfigEntry, GoodweUpdateCoordinator
from .goodwe_dt_lib import settings


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GoodweConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the GoodWe DT number entities."""
    data = config_entry.runtime_data
    async_add_entities(
        [GoodweGridExportLimitNumber(data.coordinator, data.device_info, data.inverter.serial_number)]
    )


class GoodweGridExportLimitNumber(CoordinatorEntity[GoodweUpdateCoordinator], NumberEntity):
    """Writable grid export limit (percent of rated power)."""

    _attr_has_entity_name = True
    _attr_name = "Grid export limit"
    _attr_native_min_value = float(settings.EXPORT_LIMIT_MIN)
    _attr_native_max_value = float(settings.EXPORT_LIMIT_MAX)
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: GoodweUpdateCoordinator,
        device_info: DeviceInfo,
        serial_number: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}-grid_export_limit-{serial_number}"
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.settings_value("grid_export_limit") is not None
        )

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.settings_value("grid_export_limit")
        return None if val is None else float(val)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_grid_export_limit(int(value))
