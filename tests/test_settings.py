import asyncio
import pytest
from goodwe_dt_lib.inverter import DtInverter
from goodwe_dt_lib import settings

class FakeTransport:
    def __init__(self):
        self.regs = {settings.GRID_EXPORT_LIMIT_REG: 10, settings.GRID_EXPORT_ENABLED_REG: 0}
        self.writes = []
    async def send_command(self, reg, count):
        return self.regs[reg].to_bytes(2, "big")
    async def write_register(self, reg, value):
        self.writes.append((reg, value)); self.regs[reg] = value

def _inv():
    inv = DtInverter("h"); inv.transport = FakeTransport(); return inv

def test_read_settings():
    inv = _inv()
    data = asyncio.run(inv.read_settings())
    assert data == {"grid_export_limit": 10, "grid_export_enabled": 0}

def test_set_grid_export_limit_writes_reg():
    inv = _inv()
    asyncio.run(inv.set_grid_export_limit(25))
    assert inv.transport.writes == [(settings.GRID_EXPORT_LIMIT_REG, 25)]

def test_set_grid_export_limit_clamps():
    inv = _inv()
    asyncio.run(inv.set_grid_export_limit(250))
    assert inv.transport.writes == [(settings.GRID_EXPORT_LIMIT_REG, 100)]
    asyncio.run(inv.set_grid_export_limit(-5))
    assert inv.transport.writes[-1] == (settings.GRID_EXPORT_LIMIT_REG, 0)
