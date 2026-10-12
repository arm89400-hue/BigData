"""Source 4 - Binance order book: top bid/ask levels for the money + gold watchlist.

Output: data/raw/orderbook/  (one row per price level: symbol, side, level, price, qty)
A point-in-time snapshot of supply/demand - useful for liquidity and spread analysis.
"""
import argparse

import pandas as pd

from ingest.common import TZ, WATCHLIST, get, log, retry, write_dataset


def fetch(symbol: str, depth: int) -> pd.DataFrame:
    book = retry(get, "/api/v3/depth", symbol=symbol, limit=depth)
    rows = []
    for side in ("bids", "asks"):
        for level, (price, qty) in enumerate(book[side], start=1):
            rows.append({"symbol": symbol, "side": side[:-1], "level": level,
                         "price": float(price), "qty": float(qty)})
    return pd.DataFrame(rows)


def main(symbols: list[str] | None = None, depth: int = 100) -> None:
    symbols = symbols or WATCHLIST
    log(f"orderbook: {len(symbols)} symbols, depth={depth}")
    df = pd.concat([fetch(s, depth) for s in symbols], ignore_index=True)
    df["fetched_at"] = pd.Timestamp.now(tz=TZ)
    write_dataset(df, "orderbook")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--depth", type=int, default=100, help="levels per side (5,10,20,50,100,...)")
    p.add_argument("--symbols", nargs="*")
    a = p.parse_args()
    main(symbols=a.symbols, depth=a.depth)
