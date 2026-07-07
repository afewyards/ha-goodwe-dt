"""Resilient asyncio UDP transport for GoodWe DT inverters + night-wake probe."""

from __future__ import annotations

import asyncio
import socket

from .modbus import (
    build_read_request,
    build_write_request,
    parse_response,
    parse_write_response,
)
from .exceptions import InverterError, RequestFailedException

_WAKE_PROBE = b"WIFIKIT-214028-READ"
_WAKE_TIMEOUT = 2.0  # seconds per attempt (kept short so tests finish quickly)


class _DatagramProtocol(asyncio.DatagramProtocol):
    """Minimal datagram protocol that resolves a Future on first received datagram."""

    def __init__(self, future: asyncio.Future) -> None:
        self._future = future
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:  # type: ignore[override]
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if not self._future.done():
            self._future.set_result(data)

    def error_received(self, exc: Exception) -> None:
        if not self._future.done():
            self._future.set_exception(exc)

    def connection_lost(self, exc: Exception | None) -> None:
        if exc is not None and not self._future.done():
            self._future.set_exception(exc)


class UdpTransport:
    """Resilient UDP transport for a single GoodWe DT inverter."""

    def __init__(
        self,
        host: str,
        port: int = 8899,
        addr: int = 0x7F,
        timeout: float = 1.0,
        retries: int = 3,
    ) -> None:
        self.host = host
        self.port = port
        self.addr = addr
        self.timeout = timeout
        self.retries = retries
        self._failures: int = 0

    async def _exchange(self, request: bytes) -> bytes:
        """Send ONE datagram and await ONE response.

        Opens a fresh asyncio datagram endpoint each call to defend against
        stale transport state.  Always closes the endpoint before returning
        or raising.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _DatagramProtocol(future),
            remote_addr=(self.host, self.port),
        )
        try:
            transport.sendto(request)
            return await asyncio.wait_for(asyncio.shield(future), self.timeout)
        finally:
            transport.close()

    async def send_command(self, reg: int, count: int) -> bytes:
        """Read *count* registers starting at *reg*.

        Attempts up to ``retries + 1`` times.  Returns the payload bytes on
        first success and resets ``self._failures`` to 0.  If every attempt
        fails, increments ``self._failures`` and raises
        :class:`~.exceptions.RequestFailedException`.
        """
        request = build_read_request(self.addr, reg, count)
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                raw = await self._exchange(request)
                payload = parse_response(raw, count)
                self._failures = 0
                return payload
            except (asyncio.TimeoutError, OSError, InverterError) as exc:
                last_exc = exc
                continue

        self._failures += 1
        raise RequestFailedException(
            f"All {self.retries + 1} attempts failed: {last_exc}",
            self._failures,
        )

    async def write_register(self, reg: int, value: int) -> None:
        """Write one 16-bit holding register (Modbus func 0x06).

        Retries up to ``retries + 1`` times. Raises RequestFailedException if
        every attempt fails. Independent of the read failure streak used by the
        night-sleep state machine (does not touch ``self._failures``).
        """
        request = build_write_request(self.addr, reg, value)
        last_exc: Exception | None = None
        for _ in range(self.retries + 1):
            try:
                raw = await self._exchange(request)
                parse_write_response(raw, reg, value)
                return
            except (asyncio.TimeoutError, OSError, InverterError) as exc:
                last_exc = exc
                continue
        raise RequestFailedException(
            f"write reg {reg:#06x}={value} failed: {last_exc}", self._failures
        )

    async def wake(self, probe_port: int = 48899) -> bool:
        """Probe the inverter's WiFi kit to wake it from sleep.

        1. Sends ``WIFIKIT-214028-READ`` unicast to ``(self.host, probe_port)``.
           Returns ``True`` if a reply arrives within ~2 s.
        2. On no reply, retries once with a broadcast to
           ``('255.255.255.255', probe_port)`` (sets ``SO_BROADCAST``).
           Returns ``True`` if that reply arrives within ~2 s.
        3. Returns ``False`` if neither attempt gets a reply or on any error.
        Never raises.
        """
        loop = asyncio.get_running_loop()

        async def _unicast_probe(host: str) -> bool:
            future: asyncio.Future[bytes] = loop.create_future()
            try:
                transport, _ = await loop.create_datagram_endpoint(
                    lambda: _DatagramProtocol(future),
                    remote_addr=(host, probe_port),
                )
            except OSError:
                return False
            try:
                transport.sendto(_WAKE_PROBE)
                await asyncio.wait_for(asyncio.shield(future), _WAKE_TIMEOUT)
                return True
            except (asyncio.TimeoutError, OSError):
                return False
            finally:
                transport.close()

        async def _broadcast_probe() -> bool:
            """Broadcast probe using a raw socket (needs SO_BROADCAST)."""
            future: asyncio.Future[bytes] = loop.create_future()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setblocking(False)
            try:
                transport, _ = await loop.create_datagram_endpoint(
                    lambda: _DatagramProtocol(future),
                    sock=sock,
                    remote_addr=("255.255.255.255", probe_port),
                )
            except OSError:
                sock.close()
                return False
            try:
                transport.sendto(_WAKE_PROBE)
                await asyncio.wait_for(asyncio.shield(future), _WAKE_TIMEOUT)
                return True
            except (asyncio.TimeoutError, OSError):
                return False
            finally:
                transport.close()

        try:
            if await _unicast_probe(self.host):
                return True
            return await _broadcast_probe()
        except Exception:
            return False
