"""
Live validation harness — our goodwe_dt_lib vs upstream goodwe oracle.

Connects SEQUENTIALLY (never concurrently — single-session dongle) to the
real inverter at 172.20.0.125:8899 and verifies:
  - Structural parity: our keys == upstream keys - {"leakage_current"}
  - Identity: serial_number and model_name match
  - Static values: work_mode, safety_country, e_total (within 0.5 kWh)
  - Time-varying values: printed side by side, NOT asserted
"""

import asyncio
import sys
import traceback

HOST = "172.20.0.125"
PORT = 8899

TIME_VARYING_KEYS = [
    "ppv",
    "vpv1",
    "ipv1",
    "vgrid1",
    "igrid1",
    "fgrid1",
    "temperature",
    "total_inverter_power",
    "house_consumption",
]


async def main() -> int:
    # Make our lib importable
    sys.path.insert(0, "custom_components/goodwe")
    from goodwe_dt_lib import connect as our_connect  # noqa: PLC0415
    import goodwe  # noqa: PLC0415

    print("=" * 60)
    print("GoodWe DT — live validation harness")
    print(f"Target: {HOST}:{PORT}")
    print("=" * 60)

    # ------------------------------------------------------------------ #
    # Step 1: Read via OUR lib
    # ------------------------------------------------------------------ #
    print("\n[1/2] Reading via goodwe_dt_lib …")
    try:
        our_inv = await our_connect(HOST, PORT, timeout=2.0, retries=3)
        ours = await our_inv.read_runtime_data()
    except Exception as exc:
        print(f"\n  ERROR — could not read from inverter via our lib: {exc}")
        traceback.print_exc()
        return 1

    print(f"  serial_number : {our_inv.serial_number}")
    print(f"  model_name    : {our_inv.model_name}")
    print(f"  firmware      : {our_inv.firmware}")
    print(f"  keys returned : {len(ours)}")

    # ------------------------------------------------------------------ #
    # Step 2: Read via UPSTREAM (sequential — wait for our session to close)
    # ------------------------------------------------------------------ #
    print("\n[2/2] Reading via upstream goodwe …")
    try:
        up_inv = await goodwe.connect(
            host=HOST, port=PORT, family="DT", timeout=2, retries=3
        )
        theirs = await up_inv.read_runtime_data()
    except Exception as exc:
        print(f"\n  ERROR — could not read from inverter via upstream goodwe: {exc}")
        traceback.print_exc()
        return 1

    print(f"  serial_number : {up_inv.serial_number}")
    print(f"  model_name    : {up_inv.model_name}")
    print(f"  keys returned : {len(theirs)}")

    # ------------------------------------------------------------------ #
    # Asserts
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60)
    print("ASSERT RESULTS")
    print("=" * 60)

    failures = []

    # --- Structural assert ---
    our_keys = set(ours.keys())
    their_keys = set(theirs.keys())
    expected_our_keys = their_keys - {"leakage_current"}
    structural_ok = our_keys == expected_our_keys

    if structural_ok:
        print(f"\n[PASS] Structural: our keys == upstream keys - {{leakage_current}} ({len(our_keys)} ids)")
    else:
        only_ours = our_keys - expected_our_keys
        only_theirs = expected_our_keys - our_keys
        print(f"\n[FAIL] Structural mismatch!")
        if only_ours:
            print(f"  Keys only in ours    : {sorted(only_ours)}")
        if only_theirs:
            print(f"  Keys missing from ours: {sorted(only_theirs)}")
        failures.append("structural")

    # --- Identity asserts ---
    serial_ok = our_inv.serial_number == up_inv.serial_number
    model_ok = our_inv.model_name == up_inv.model_name

    if serial_ok:
        print(f"[PASS] Identity serial_number: {our_inv.serial_number!r}")
    else:
        print(f"[FAIL] Identity serial_number: ours={our_inv.serial_number!r} upstream={up_inv.serial_number!r}")
        failures.append("serial_number")

    if model_ok:
        print(f"[PASS] Identity model_name: {our_inv.model_name!r}")
    else:
        print(f"[FAIL] Identity model_name: ours={our_inv.model_name!r} upstream={up_inv.model_name!r}")
        failures.append("model_name")

    # --- Static cross-check asserts ---
    static_fields = ["work_mode", "work_mode_label", "safety_country", "safety_country_label"]
    for field in static_fields:
        our_val = ours.get(field)
        their_val = theirs.get(field)
        if our_val == their_val:
            print(f"[PASS] Static {field}: {our_val!r}")
        else:
            print(f"[FAIL] Static {field}: ours={our_val!r} upstream={their_val!r}")
            failures.append(f"static_{field}")

    # e_total within 0.5 kWh
    our_etotal = ours.get("e_total")
    their_etotal = theirs.get("e_total")
    if our_etotal is not None and their_etotal is not None:
        delta = abs(float(our_etotal) - float(their_etotal))
        if delta <= 0.5:
            print(f"[PASS] Static e_total: ours={our_etotal} upstream={their_etotal} (delta={delta:.3f} kWh ≤ 0.5)")
        else:
            print(f"[FAIL] Static e_total: ours={our_etotal} upstream={their_etotal} (delta={delta:.3f} kWh > 0.5)")
            failures.append("e_total")
    else:
        print(f"[FAIL] Static e_total: one or both values missing (ours={our_etotal}, upstream={their_etotal})")
        failures.append("e_total_missing")

    # ------------------------------------------------------------------ #
    # Time-varying: print only, DO NOT assert
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60)
    print("TIME-VARYING VALUES (print only — differ between sequential reads)")
    print("=" * 60)
    print(f"  {'Key':<30}  {'Ours':>12}  {'Upstream':>12}")
    print(f"  {'-'*30}  {'-'*12}  {'-'*12}")
    for key in TIME_VARYING_KEYS:
        our_val = ours.get(key, "N/A")
        their_val = theirs.get(key, "N/A")
        print(f"  {key:<30}  {str(our_val):>12}  {str(their_val):>12}")

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60)
    if failures:
        print(f"RESULT: FAILED — {len(failures)} assertion(s) failed: {failures}")
        print("=" * 60)
        return 1
    else:
        print("RESULT: ALL ASSERTS PASSED")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(asyncio.wait_for(main(), timeout=90))
    except asyncio.TimeoutError:
        print("\nFATAL: Overall 90-second timeout exceeded — inverter may be unreachable.")
        exit_code = 1
    except Exception as exc:
        print(f"\nFATAL: Unexpected error: {exc}")
        traceback.print_exc()
        exit_code = 1

    sys.exit(exit_code)
