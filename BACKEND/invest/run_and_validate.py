"""
run_and_validate.py
====================
Runs insert -> validate for ONE endpoint at a time, per symbol, so the gap
between "insert.py fetched this live" and "validate.py fetched this live
again" stays a few seconds instead of accumulating across a full 10-endpoint
pass. This is the automated version of the "table by table" check you ran
by hand that already matched every time.

It imports insert.py and validate_dynamo.py directly (no changes made to
either file) and calls their existing functions in an interleaved order.

Usage
-----
    python run_and_validate.py --symbols TCS INFY
    python run_and_validate.py --symbols TCS --endpoints stock-page stock-chart
    python run_and_validate.py --symbols TCS --dry-run          # insert only, skip DB writes (also skips validate)
    python run_and_validate.py --symbols TCS --diff             # show field-level diff on mismatch
    python run_and_validate.py --symbols TCS --live-snapshots   # run live snapshots only (price + SI + options)

Requires FLASK_BASE_URL (env var, default http://localhost:5000) to point at
a running instance of your Flask app, same as validate_dynamo.py normally
needs.
"""

import argparse
import time
import traceback

import insert as ins
import validate_dynamo as val


def build_parser():
    p = argparse.ArgumentParser(description="Interleaved insert -> validate, one endpoint at a time.")
    p.add_argument("--symbols", nargs="+", default=None, help="Symbols to process (default: all from stock_list.csv)")
    p.add_argument("--endpoints", nargs="+", default=ins.ALL_ENDPOINTS, choices=ins.ALL_ENDPOINTS)
    p.add_argument("--period", default="1y")
    p.add_argument("--interval", default="1d")
    p.add_argument("--expiry", default=None)
    p.add_argument("--peers", nargs="+", default=None)
    p.add_argument("--dry-run", action="store_true", help="Fetch only, skip DynamoDB writes AND validation")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--diff", action="store_true")
    p.add_argument("--pause", type=float, default=1.0, help="Seconds to wait between insert and validate for the same endpoint (default: 1.0)")
    p.add_argument("--live-snapshots", action="store_true",
                   help="Run live snapshots only (price + short-interest + options). "
                        "Skips the normal insert-validate loop.")
    return p


def main():
    args = build_parser().parse_args()

    all_stocks = ins.load_symbol()
    if not all_stocks:
        print("[ERROR] No symbols loaded. Check stock_list.csv path.")
        return

    if args.symbols:
        requested = [s.upper() for s in args.symbols]
        symbols = [s for s in all_stocks if s["SYMBOL"] in requested]
        if not symbols:
            print(f"[ERROR] None of {requested} found in stock_list.csv")
            return
    else:
        symbols = all_stocks

    # ── Live-snapshot fast path ──────────────────────────────────────────────
    if args.live_snapshots:
        from datetime import datetime, timezone
        symbol_names = [s["SYMBOL"] if isinstance(s, dict) else s for s in symbols]
        print(f"\n{'='*60}")
        print(f"  LIVE SNAPSHOTS")
        print(f"  Symbols     : {', '.join(symbol_names)}")
        print(f"  Started at  : {datetime.now(timezone.utc).isoformat()} UTC")
        print(f"{'='*60}")
        ins.run_live_snapshots(symbol_names)
        print(f"\n{'='*60}")
        print(f"  DONE — {datetime.now(timezone.utc).isoformat()} UTC")
        print(f"{'='*60}\n")
        return

    results = []

    for stock in symbols:
        symbol = stock["SYMBOL"]
        print(f"\n{'─' * 60}")
        print(f"  Symbol: {symbol}")
        print(f"{'─' * 60}")

        for endpoint in args.endpoints:
            # ---- 1. insert this one endpoint ----
            t0 = time.time()
            try:
                ins.run_endpoint(endpoint, symbol, args, args.dry_run, args.skip_existing)
            except Exception as e:
                print(f"    [INSERT ERROR] {endpoint}: {e}")
                traceback.print_exc()
                continue
            insert_elapsed = time.time() - t0

            if args.dry_run:
                print(f"    -> {endpoint} inserted (dry run) in {insert_elapsed:.1f}s, skipping validate")
                continue

            # small pause so DynamoDB's write is guaranteed visible on read
            time.sleep(args.pause)

            # ---- 2. validate this same endpoint, right away ----
            validator = val.VALIDATORS.get(endpoint)
            if not validator:
                print(f"    [SKIP] no validator registered for {endpoint}")
                continue

            try:
                validator(symbol, args, results)
            except Exception as e:
                print(f"    [VALIDATE ERROR] {endpoint}: {e}")
                traceback.print_exc()

            # keep the normal insert rate-limit pause between endpoints
            time.sleep(0.5)

        time.sleep(1)

    val.print_summary(results, only_mismatches=False)


if __name__ == "__main__":
    main()
