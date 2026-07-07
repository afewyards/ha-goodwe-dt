# GoodWe DT Inverter (resilient) — Home Assistant integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
![HA version](https://img.shields.io/badge/Home%20Assistant-2024.1.0%2B-41BDF5.svg)

A local-polling Home Assistant integration for **GoodWe DT-family** string inverters
(e.g. `GW3000-DNS-30`). It talks Modbus/UDP directly to the inverter on your LAN — **no
cloud, no SEMS account** — and is built to stay healthy through the inverter's nightly
sleep, which is where most GoodWe integrations get noisy.

> **Drop-in replacement.** This integration uses the `goodwe` domain and the *same*
> entity `unique_id`s as the official/previous GoodWe integration, so your dashboards,
> history and automations carry straight over. Because it shares the `goodwe` domain,
> you must remove the official GoodWe integration first — the two cannot run side by side.

## Why "resilient"?

DT inverters are solar-only: at night they power down and stop answering. A naive poller
then floods the log with errors and marks every entity *unavailable*. This integration
instead:

- **Backs off gracefully.** After 3 consecutive failed polls the inverter is declared
  `ASLEEP` and polling slows from 30 s to 5 min, sending a wake-probe before each retry.
- **Keeps your energy stats readable.** Daily/total energy sensors stay *available* through
  the night, holding their last value instead of dropping to unavailable.
- **Handles the day rollover itself.** "Today's PV Generation" resets to 0 at local
  midnight even though the inverter is asleep and can't zero it.
- **Recovers automatically** at sunrise once the inverter answers again.

## Features

- 🔌 **Local polling** over Modbus/UDP (default port `8899`, Modbus address `0x7f`) — fully offline.
- 🖥️ **UI config flow** — set up by IP; serial number is auto-discovered as the unique ID.
- ⚙️ **Options flow** — change host / port / scan interval after setup, no reinstall.
- 📊 **~50 sensors** across the runtime block, meter block, and calculated values.
- 📈 **Energy Dashboard ready** — energy sensors are `total_increasing`.
- 📝 **Writable grid export limit** — a `number` entity (% of rated power) plus a read-only
  "Grid export enabled" diagnostic sensor.

### Entities

**Primary sensors:** PV Power, House Consumption, Today's / Total PV Generation, Meter Total
Export / Import Energy.

**Diagnostic sensors** (disabled from the primary view but available): per-string PV
voltage/current/power (PV1, PV2), per-phase grid voltage/current/frequency/power (L1–L3),
total inverter power, work mode, error & warning codes, apparent/reactive power, power
factor, inverter & heatsink temperature, total running hours, safety country, bus voltages,
derating mode, RSSI, meter active power, and meter communication status.

**Controls:** `number.*_grid_export_limit` (0–100 %).

## Requirements

- Home Assistant **2024.1.0** or newer.
- A GoodWe **DT-family** inverter reachable on your network with port **8899/UDP** open
  (single-phase and three-phase DT string inverters; tested on `GW3000-DNS-30`).
- A static IP / DHCP reservation for the inverter is recommended.

## Installation

### HACS (recommended)

1. In HACS → **Integrations**, open the ⋮ menu → **Custom repositories**.
2. Add `https://github.com/kleist/ha-goodwe-dt` with category **Integration**.
3. Search for **GoodWe DT Inverter**, install it, and **restart Home Assistant**.

### Manual

Copy `custom_components/goodwe` into your Home Assistant `config/custom_components/`
directory (so you end up with `config/custom_components/goodwe/`), then restart.

## Configuration

1. **Settings → Devices & Services → Add Integration → GoodWe DT Inverter.**
2. Enter the inverter's **IP address**. Port (`8899`) and scan interval (`30 s`) are
   pre-filled — adjust only if needed.
3. Submit. The integration connects, reads the serial/model, and creates the device.

| Option | Default | Notes |
|---|---|---|
| Host | — | Inverter IP address |
| Port | `8899` | GoodWe UDP Modbus port (DT family) |
| Scan interval | `30 s` | Daytime poll cadence; auto-slows to 5 min while asleep |

## Contributing

Issues and pull requests are welcome:
<https://github.com/kleist/ha-goodwe-dt/issues>

## License

See the repository for license details.
