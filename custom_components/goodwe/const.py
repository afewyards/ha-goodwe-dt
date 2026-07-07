"""Constants for the GoodWe DT integration."""

from homeassistant.const import Platform

DOMAIN = "goodwe"

PLATFORMS = [Platform.SENSOR, Platform.NUMBER]

# Polling / recovery timing (seconds)
DEFAULT_SCAN_INTERVAL = 30        # daytime poll cadence
NIGHT_RECOVERY_INTERVAL = 300     # cadence while inverter is asleep (wake-probe + retry)
ASLEEP_AFTER = 3                  # consecutive failed polls before declaring ASLEEP

# Network
DEFAULT_PORT = 8899               # GoodWe UDP Modbus port (DT family)
DEFAULT_NETWORK_TIMEOUT = 1.0
DEFAULT_NETWORK_RETRIES = 3
DEFAULT_MODBUS_ADDR = 0x7f        # DT family Modbus address

# Config entry keys
CONF_SCAN_INTERVAL = "scan_interval"
CONF_NETWORK_TIMEOUT = "network_timeout"
CONF_NETWORK_RETRIES = "network_retries"
