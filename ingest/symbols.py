"""Source 1 - Binance exchangeInfo: the universe of tradable markets.

Output: data/raw/symbols/  (one row per trading pair: base/quote asset, status, type)
This is the crypto equivalent of a securities master; other jobs read it via load_symbols().
"""
from ingest.common import get, log, write_dataset
import pandas as pd


def main() -> None:
    log("symbols: fetching exchangeInfo")
    info = get("/api/v3/exchangeInfo")
    rows = [{
        "symbol": s["symbol"],
        "base_asset": s["baseAsset"],
        "quote_asset": s["quoteAsset"],
        "status": s["status"],
        "is_spot": s.get("isSpotTradingAllowed", False),
        "is_margin": s.get("isMarginTradingAllowed", False),
    } for s in info["symbols"]]
    df = pd.DataFrame(rows).sort_values("symbol")
    trading = (df["status"] == "TRADING").sum()
    log(f"symbols: {len(df):,} pairs ({trading:,} TRADING)")
    write_dataset(df, "symbols")


if __name__ == "__main__":
    main()
