#!/usr/bin/env python3
"""Standalone night-soak logger for a GoodWe DT inverter.

Captures the dusk -> overnight -> dawn lifecycle to answer the questions the
recovery design depends on:

  * When does the inverter go silent at dusk?
  * In the morning, does the dongle wake on its own, or only after a
    WIFIKIT-214028-READ probe to :48899?
  * What does the inverter's own clock (`timestamp` sensor) read on wake
    (i.e. does its RTC drift/reset over a power-off night)?

It is intentionally independent of the re-derived library: it uses the
upstream `goodwe` package as the reader and a raw UDP socket for the wake
probe. Run it before dusk and leave it running overnight.

Usage:
    python scripts/night_soak_standalone.py [HOST] [--interval SEC] [--cycles N]

Defaults: HOST=172.20.0.125, interval=60s, cycles=0 (run forever).
Requires the `goodwe` package:  pip install goodwe==0.4.10
Logs to stdout and appends to scripts/night-soak-<YYYY-MM-DD>.log next to this file.
"""
from __future__ import annotations

import argparse
import asyncio
import socket
from datetime import datetime
from pathlib import Path

try:
    import goodwe  # type: ignore[import]
except ImportError:  # pragma: no cover
    raise SystemExit("Missing dependency. Install with: pip install goodwe==0.4.10")

PORT = 8899
PROBE_PORT = 48899
PROBE = b"WIFIKIT-214028-READ"

LOG_PATH = Path(__file__).with_name(f"night-soak-{datetime.now():%Y-%m-%d}.log")


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a") as fp:
        fp.write(line + "\n")


def wake_probe(host: str, timeout: float = 3.0) -> str | None:
    """Send the unicast wake probe; return the reply string or None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(PROBE, (host, PROBE_PORT))
        data, _ = s.recvfrom(1024)
        return data.decode(errors="replace")
    except socket.timeout:
        return None
    except OSError as exc:
        return f"ERR:{exc}"
    finally:
        s.close()


async def read_once(host: str):
    """Fresh connect + runtime read. Returns (ok, data_or_exc)."""
    try:
        inv = await goodwe.connect(host=host, port=PORT, family="DT", timeout=2, retries=3)
        data = await inv.read_runtime_data()
        return True, data
    except Exception as exc:  # noqa: BLE001 - we want to log any failure
        return False, exc


def summarize(data) -> str:
    g = lambda k: data.get(k)
    return (
        f"inv_clock={g('timestamp')} ppv={g('ppv')}W "
        f"e_day={g('e_day')}kWh e_total={g('e_total')}kWh "
        f"work_mode={g('work_mode_label')} vpv1={g('vpv1')}V vgrid1={g('vgrid1')}V"
    )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("host", nargs="?", default="172.20.0.125")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--cycles", type=int, default=0, help="0 = run forever")
    args = ap.parse_args()

    log(f"=== night-soak start host={args.host} interval={args.interval}s "
        f"cycles={args.cycles or 'inf'} log={LOG_PATH.name} ===")

    state = "INIT"
    n = 0
    while True:
        n += 1
        bare_ok, bare = await read_once(args.host)

        if bare_ok:
            if state == "ASLEEP":
                log(f"*** SELF_WAKE — bare read succeeded with no probe. {summarize(bare)}")
            else:
                log(f"AWAKE  {summarize(bare)}")
            state = "AWAKE"
        else:
            log(f"read_fail: {type(bare).__name__}: {bare}")
            reply = wake_probe(args.host)
            log(f"  wake_probe -> {reply if reply else 'TIMEOUT (no reply)'}")
            post_ok, post = await read_once(args.host)
            if post_ok:
                log(f"*** PROBE_WAKE — read succeeded after probe. {summarize(post)}")
                state = "AWAKE"
            else:
                if state != "ASLEEP":
                    log(f"*** WENT ASLEEP — {type(post).__name__}: {post}")
                else:
                    log(f"  still asleep ({type(post).__name__})")
                state = "ASLEEP"

        if args.cycles and n >= args.cycles:
            log(f"=== night-soak done after {n} cycles (final state {state}) ===")
            return
        await asyncio.sleep(args.interval)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("=== night-soak interrupted by user ===")
