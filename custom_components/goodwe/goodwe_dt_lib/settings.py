"""Writable inverter settings (holding registers, Modbus func 0x03 read / 0x06 write).

Register choice mirrors the upstream `goodwe` library's *three-phase* DT settings,
because it classifies GW3000-DNS-30 as three-phase — so the official integration
exposed grid_export_limit at 40336 (%). We match it for drop-in parity.
"""

GRID_EXPORT_LIMIT_REG = 40336    # Integer, percent
GRID_EXPORT_ENABLED_REG = 40327  # Integer, 0=off 1=on

EXPORT_LIMIT_MIN = 0
EXPORT_LIMIT_MAX = 100
