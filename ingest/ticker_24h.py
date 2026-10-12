"""Source 3 - Binance 24h ticker: a market-wide snapshot of every symbol's last 24 hours.

Output: data/raw/ticker_24h/  (one row per symbol: price change %, high/low, volume, trades)
A single call returns all ~3,000 markets at once - a cheap, broad "state of the market" table.
"""
import pandas as pd

from ingest.common import TZ, get, log, write_dataset

NUMERIC = ["price_change", "price_change_pct", "weighted_avg_price", "last_price",
           "open_price", "high_price", "low_price", "volume", "quote_volume"]
RENAME = {
    "priceChange": "price_change", "priceChangePercent": "price_change_pct",
    "weightedAvgPrice": "weighted_avg_price", "lastPrice": "last_price",
    "openPrice": "open_price", "highPrice": "high_price", "lowPrice": "low_price",
    "volume": "volume", "quoteVolume": "quote_volume", "count": "trades",
}


def main() -> None:
    log("ticker_24h: fetching all-market snapshot")
    data = get("/api/v3/ticker/24hr")
    df = pd.DataFrame(data).rename(columns=RENAME)
    df = df[["symbol", *RENAME.values()]].copy()
    df[NUMERIC] = df[NUMERIC].astype(float)
    df["trades"] = df["trades"].astype(int)
    df["fetched_at"] = pd.Timestamp.now(tz=TZ)
    df = df.sort_values("quote_volume", ascending=False)
    log(f"ticker_24h: {len(df):,} markets")
    write_dataset(df, "ticker_24h")


if __name__ == "__main__":
    main()
