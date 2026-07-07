import asyncio
import pytest
from goodwe_dt_lib.protocol import UdpTransport
from goodwe_dt_lib.exceptions import RequestFailedException

# a valid 15-reg meter frame (aa55 7f 03 1e <30 bytes> crc) for parse to accept
METER_FRAME = bytes.fromhex("aa557f031e0000000000000000000000000000ffff00000000ffffffff0000ffff00001e70")


async def test_send_command_ok(monkeypatch):
    t = UdpTransport("127.0.0.1")
    async def fake(req): return METER_FRAME
    monkeypatch.setattr(t, "_exchange", fake)
    payload = await t.send_command(0x75f3, 0x0f)
    assert len(payload) == 30
    assert t._failures == 0


async def test_send_command_retries_then_fails_and_counts(monkeypatch):
    t = UdpTransport("127.0.0.1", retries=2)
    async def always_timeout(req): raise asyncio.TimeoutError
    monkeypatch.setattr(t, "_exchange", always_timeout)
    with pytest.raises(RequestFailedException) as ei:
        await t.send_command(0x75f3, 0x0f)
    assert ei.value.consecutive_failures_count == 1
    with pytest.raises(RequestFailedException) as ei2:
        await t.send_command(0x75f3, 0x0f)
    assert ei2.value.consecutive_failures_count == 2


async def test_send_command_recovers_resets_count(monkeypatch):
    t = UdpTransport("127.0.0.1", retries=1)
    calls = {"n": 0}
    async def flaky(req):
        calls["n"] += 1
        if calls["n"] == 1: raise asyncio.TimeoutError
        return METER_FRAME
    monkeypatch.setattr(t, "_exchange", flaky)
    payload = await t.send_command(0x75f3, 0x0f)   # 1st attempt times out, 2nd succeeds
    assert len(payload) == 30 and t._failures == 0


async def test_wake_unicast_true():
    # loopback fake discovery responder on an ephemeral port
    loop = asyncio.get_running_loop()
    class Resp(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr): self.transport.sendto(b"127.0.0.1,AABBCC,Solar", addr)
        def connection_made(self, transport): self.transport = transport
    server, _ = await loop.create_datagram_endpoint(Resp, local_addr=("127.0.0.1", 0))
    port = server.get_extra_info("socket").getsockname()[1]
    try:
        t = UdpTransport("127.0.0.1")
        assert await t.wake(probe_port=port) is True
    finally:
        server.close()


async def test_wake_no_responder_false():
    t = UdpTransport("127.0.0.1")
    # nothing listening on this port -> unicast no reply, broadcast no reply -> False
    assert await t.wake(probe_port=49999) is False
