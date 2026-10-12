"""Near-realtime feed - Binance 1-minute klines, polled continuously (crypto trades 24/7).

Each poll fetches the most recent minute bars for the watchlist and appends only the closed
bars not saved before. Unlike Yahoo, Binance keeps full 1m history, so you can also just pull
it with prices_daily.py --interval 1m - this job is for a live, streaming-into-Spark demo.

Output: data/raw/prices_intraday/date=YYYY-MM-DD/bars_HHMMSS.parquet
        (ts, symbol, open, high, low, close, volume, trades) - Spark can stream this folder.

Run:  python -m ingest.prices_intraday                      # watchlist, poll every 1 min
      python -m ingest.prices_intraday --symbols PAXGUSDT BTCUSDT --every 5
      python -m ingest.prices_intraday --once                # one poll now, then exit
"""
import argparse
import time

import pandas as pd

from ingest.common import RAW, TZ, WATCHLIST, get, log, read_dataset, retry

OUT = RAW / "prices_intraday"
RECENT = 120  # minute bars to request per poll; plenty of overlap so nothing is missed


def load_last_seen(day: str) -> pd.Series:
    saved = read_dataset(OUT / f"date={day}", columns=["symbol", "ts"])
    if saved.empty:
        return pd.Series(dtype=f"datetime64[ns, {TZ}]")
    return saved.groupby("symbol")["ts"].max()


def fetch(symbol: str) -> pd.DataFrame:
    rows = retry(get, "/api/v3/klines", symbol=symbol, interval="1m", limit=RECENT)
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume",
                                     "close_time", "qv", "trades", "tbb", "tbq", "ig"])
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.tz_convert(TZ)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True).dt.tz_convert(TZ)
    df["symbol"] = symbol
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    df["trades"] = df["trades"].astype(int)
    return df


def poll(symbols: list[str]) -> pd.DataFrame:
    bars = pd.concat([fetch(s) for s in symbols], ignore_index=True)
    # Keep only bars whose minute has fully closed; the current minute is still forming.
    now = pd.Timestamp.now(tz=TZ)
    bars = bars[bars["close_time"] <= now]
    return bars[["ts", "symbol", "open", "high", "low", "close", "volume", "trades"]]


def only_new(bars: pd.DataFrame, last_seen: pd.Series) -> pd.DataFrame:
    if last_seen.empty:
        return bars
    seen = bars["symbol"].map(last_seen)
    return bars[seen.isna() | (bars["ts"] > seen)]


def main(symbols: list[str], every: float, once: bool) -> None:
    log(f"intraday: {len(symbols)} symbols, poll every {every} min")
    while True:
        now = pd.Timestamp.now(tz=TZ)
        bars = poll(symbols)
        days = bars.groupby(bars["ts"].dt.strftime("%Y-%m-%d")) if not bars.empty else []
        saved = 0
        for bar_day, part in days:
            part = only_new(part, load_last_seen(bar_day))
            if part.empty:
                continue
            folder = OUT / f"date={bar_day}"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"bars_{now:%H%M%S}.parquet"
            part.to_parquet(path, index=False)
            saved += len(part)
            log(f"intraday: +{len(part):,} bars -> {path.relative_to(RAW.parent.parent)}")
        if not saved:
            log("intraday: no new closed bars")
        if once:
            break
        time.sleep(every * 60)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", nargs="*", help="default: the money + gold watchlist")
    p.add_argument("--every", type=float, default=1, help="minutes between polls")
    p.add_argument("--once", action="store_true", help="poll once and exit")
    a = p.parse_args()
    main([s.upper() for s in a.symbols] if a.symbols else WATCHLIST, a.every, a.once)
