"""Source 2 - Binance klines: full DAILY OHLCV history for the money + gold watchlist.

Output: data/raw/prices_daily/year=YYYY/  (one row per symbol per day)
Gold enters here as PAXGUSDT (1 token = 1 troy oz), alongside major crypto and fiat pairs.

--all-usdt scans every USDT-quoted pair instead of the watchlist (hundreds of symbols -
genuinely "big data": hundreds of pairs x ~2,500 days). Needs ingest.symbols to have run.
"""
import argparse

import pandas as pd

from ingest.common import WATCHLIST, get, load_symbols, log, retry, write_dataset

# Binance returns at most 1000 candles per klines call, so history is paged by start time.
LIMIT = 1000
KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]
NUMERIC = ["open", "high", "low", "close", "volume", "quote_volume",
           "taker_buy_base", "taker_buy_quote"]


def fetch_klines(symbol: str, interval: str) -> list[list]:
    """All candles for symbol since listing, paging forward until Binance returns a short page."""
    out, start = [], 0
    while True:
        page = retry(get, "/api/v3/klines", symbol=symbol, interval=interval,
                     startTime=start, limit=LIMIT)
        if not page:
            break
        out.extend(page)
        if len(page) < LIMIT:
            break
        start = page[-1][0] + 1  # one ms past the last candle's open time
    return out


def to_frame(symbol: str, rows: list[list]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=KLINE_COLS).drop(columns="ignore")
    df["symbol"] = symbol
    df[NUMERIC] = df[NUMERIC].astype(float)
    df["trades"] = df["trades"].astype(int)
    df["date"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.date
    df["year"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.year
    return df


def main(symbols: list[str] | None = None, interval: str = "1d", all_usdt: bool = False) -> None:
    if symbols is None:
        symbols = load_symbols(quote="USDT") if all_usdt else WATCHLIST
    log(f"prices_daily: {len(symbols)} symbols, interval={interval}")
    frames, missing = [], []
    for n, symbol in enumerate(symbols, start=1):
        rows = fetch_klines(symbol, interval)
        if not rows:
            missing.append(symbol)
            continue
        frames.append(to_frame(symbol, rows))
        if n % 25 == 0 or n == len(symbols):
            log(f"  {n}/{len(symbols)} done, last={symbol} ({len(rows):,} candles)")

    df = pd.concat(frames, ignore_index=True)
    df = df[["symbol", "date", "open", "high", "low", "close", "volume", "quote_volume",
             "trades", "taker_buy_base", "taker_buy_quote", "year"]]
    df = df.sort_values(["symbol", "date"])
    if missing:
        log(f"prices_daily: no data for {missing}")
    # Daily -> prices_daily; any finer interval gets its own folder, e.g. prices_1h.
    name = "prices_daily" if interval == "1d" else f"prices_{interval}"
    write_dataset(df, name, partition_col="year")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--interval", default="1d", help="1d, 1w, 1M, 4h ...")
    p.add_argument("--all-usdt", action="store_true", help="scan every USDT pair, not the watchlist")
    p.add_argument("--symbols", nargs="*", help="explicit symbols, e.g. PAXGUSDT BTCUSDT")
    a = p.parse_args()
    main(symbols=a.symbols, interval=a.interval, all_usdt=a.all_usdt)
