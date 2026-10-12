"""Pull every batch source from Binance into data/raw/ and print a size summary.

Run:  python run_batch.py                         # everything
      python run_batch.py --only symbols prices    # selected jobs
      python run_batch.py --all-usdt                # scan every USDT pair, not just the watchlist
"""
import argparse

import pyarrow.parquet as pq

from ingest import orderbook, prices_daily, symbols, ticker_24h
from ingest.common import RAW, log

JOBS = {
    "symbols": symbols.main,       # must run first - other jobs read data/raw/symbols
    "prices": prices_daily.main,   # daily OHLCV history (gold + crypto + fiat)
    "ticker": ticker_24h.main,     # all-market 24h snapshot
    "orderbook": orderbook.main,   # watchlist order-book depth snapshot
}


def summary() -> None:
    print("\n=== data/raw summary ===")
    total_rows = total_mb = 0
    for folder in sorted(p for p in RAW.iterdir() if p.is_dir() and not p.name.startswith("_")):
        files = list(folder.rglob("*.parquet"))
        if not files:
            continue
        rows = sum(pq.ParquetFile(f).metadata.num_rows for f in files)
        mb = sum(f.stat().st_size for f in files) / 1e6
        total_rows += rows
        total_mb += mb
        print(f"{folder.name:22} {rows:>12,} rows {mb:>9.1f} MB")
    print(f"{'TOTAL':22} {total_rows:>12,} rows {total_mb:>9.1f} MB")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", choices=list(JOBS), help="default: all jobs")
    p.add_argument("--all-usdt", action="store_true",
                   help="daily prices: scan every USDT pair instead of the watchlist")
    a = p.parse_args()
    for name in a.only or list(JOBS):
        if name == "prices":
            prices_daily.main(all_usdt=a.all_usdt)
        else:
            JOBS[name]()
    log("batch done")
    summary()
