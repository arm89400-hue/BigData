"""Source 2b - Binance klines: HOURLY OHLCV history for USDT pairs (the ~13.8M-row set).

Output: data/raw/prices_1h/year=YYYY/part-<symbol>.parquet

Memory-safe: each symbol is written straight to disk as soon as it is fetched, so only one
symbol is ever held in RAM (prices_daily concatenates everything first, which runs out of
memory at this size). Builds in a temp dir, then swaps it in.

Run:  python -m ingest.prices_hourly              # every USDT pair (~506)
      python -m ingest.prices_hourly --top 80     # top 80 pairs by 24h quote volume
"""
import argparse
import shutil

from ingest.common import RAW, load_symbols, log, read_dataset
from ingest.prices_daily import fetch_klines, to_frame

COLS = ["symbol", "date", "open", "high", "low", "close", "volume", "quote_volume",
        "trades", "taker_buy_base", "taker_buy_quote"]


def main(top: int | None = None, interval: str = "1h") -> None:
    symbols = load_symbols(quote="USDT")
    if top:
        t = read_dataset(RAW / "ticker_24h")
        t = t[t["symbol"].isin(set(symbols))].sort_values("quote_volume", ascending=False)
        symbols = t["symbol"].tolist()[:top]
    name = f"prices_{interval}"
    target, tmp = RAW / name, RAW / f"_{name}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    log(f"prices_hourly: {len(symbols)} USDT pairs, interval={interval} (streaming to disk)")

    total = 0
    for i, symbol in enumerate(symbols, start=1):
        rows = fetch_klines(symbol, interval)
        if not rows:
            continue
        df = to_frame(symbol, rows)
        for year, part in df.groupby("year"):
            folder = tmp / f"year={year}"
            folder.mkdir(exist_ok=True)
            part[COLS].to_parquet(folder / f"part-{symbol}.parquet", index=False)
        total += len(df)
        if i % 25 == 0 or i == len(symbols):
            log(f"  {i}/{len(symbols)} done, last={symbol}, running total={total:,} rows")

    shutil.rmtree(target, ignore_errors=True)
    tmp.rename(target)
    log(f"saved {name}: {total:,} rows -> {target}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, help="only the top N USDT pairs by 24h quote volume")
    p.add_argument("--interval", default="1h")
    a = p.parse_args()
    main(top=a.top, interval=a.interval)
