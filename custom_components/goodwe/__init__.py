"""The GoodWe DT inverter integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_NETWORK_RETRIES,
    CONF_NETWORK_TIMEOUT,
    DEFAULT_NETWORK_RETRIES,
    DEFAULT_NETWORK_TIMEOUT,
    DEFAULT_PORT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import GoodweConfigEntry, GoodweRuntimeData, GoodweUpdateCoordinator
from .goodwe_dt_lib import connect
from .goodwe_dt_lib.exceptions import InverterError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: GoodweConfigEntry) -> bool:
    """Set up GoodWe DT from a config entry."""
    host = entry.options.get(CONF_HOST, entry.data[CONF_HOST])
    port = entry.options.get(CONF_PORT, entry.data.get(CONF_PORT, DEFAULT_PORT))
    timeout = entry.options.get(CONF_NETWORK_TIMEOUT, DEFAULT_NETWORK_TIMEOUT)
    retries = entry.options.get(CONF_NETWORK_RETRIES, DEFAULT_NETWORK_RETRIES)

    try:
        inverter = await connect(host=host, port=port, timeout=timeout, retries=retries)
    except InverterError as err:
        raise ConfigEntryNotReady(f"Cannot connect to GoodWe DT inverter at {host}") from err

    device_info = DeviceInfo(
        configuration_url="https://semsplus.goodwe.com/",
        identifiers={(DOMAIN, inverter.serial_number)},
        name=entry.title,
        manufacturer="GoodWe",
        model=inverter.model_name,
        sw_version=inverter.firmware,
        hw_version=f"{inverter.serial_number[5:8]} {inverter.serial_number[0:5]}",
    )

    coordinator = GoodweUpdateCoordinator(hass, entry, inverter)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = GoodweRuntimeData(
        inverter=inverter,
        coordinator=coordinator,
        device_info=device_info,
    )

    entry.async_on_unload(entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GoodweConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: GoodweConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: GoodweConfigEntry) -> bool:
    """Migrate old config entries.

    This integration reuses the ``goodwe`` domain as a drop-in replacement, so an
    entry created by the previous integration may be loaded here. We only require a
    host (and tolerate a missing port, defaulting to the DT UDP port), so existing
    entries load without transformation.
    """
    if entry.version > 2:
        return False
    if CONF_HOST not in entry.data:
        _LOGGER.error("Config entry %s has no host; cannot migrate", entry.entry_id)
        return False
    # Bring older (v1) entries up to v2; ensure a port is present.
    new_data = {**entry.data}
    new_data.setdefault(CONF_PORT, DEFAULT_PORT)
    hass.config_entries.async_update_entry(entry, data=new_data, version=2)
    return True
