"""Data catalog for the Binance market-data lake, plus a grouped display of it.

Two catalogs:
  DATASETS      - the Parquet datasets in data/raw/, grouped by category
  ASSET_CLASSES - the watchlist instruments, grouped by asset class (gold / crypto / fiat)

Run:  python catalog.py            # print the catalog + a live price snapshot, grouped
      python catalog.py --md       # also (re)write CATALOG.md

Row counts are from the last full scan (pyarrow is blocked by Application Control on this
machine, so they are stored constants); sizes are read live from disk.
"""
import argparse
import json
from pathlib import Path

import requests

from ingest.common import RAW, BASE, GOLD, CRYPTO, FIAT

SOURCE = "Binance public API  (data-api.binance.vision / api.binance.com)"

# rows captured at the last full --all-usdt scan
ROWS = {"symbols": 3724, "prices_daily": 41066, "prices_1h": 13795748,
        "ticker_24h": 3727, "orderbook": 2800, "prices_intraday": 238}

DATASETS = {
    "Reference / master data": [
        {"name": "symbols", "grain": "one row per trading pair", "endpoint": "/api/v3/exchangeInfo",
         "cols": ["symbol", "base_asset", "quote_asset", "status", "is_spot", "is_margin"]},
    ],
    "Price history (OHLCV)": [
        {"name": "prices_daily", "grain": "one row per symbol per day", "endpoint": "/api/v3/klines (1d)",
         "cols": ["symbol", "date", "open", "high", "low", "close", "volume", "quote_volume", "trades", "year"]},
        {"name": "prices_1h", "grain": "one row per symbol per hour", "endpoint": "/api/v3/klines (1h)",
         "cols": ["symbol", "date", "open", "high", "low", "close", "volume", "quote_volume", "trades", "year"]},
    ],
    "Market snapshots": [
        {"name": "ticker_24h", "grain": "one row per market, point-in-time", "endpoint": "/api/v3/ticker/24hr",
         "cols": ["symbol", "last_price", "price_change_pct", "high_price", "low_price", "volume", "quote_volume", "trades", "fetched_at"]},
        {"name": "orderbook", "grain": "one row per price level, point-in-time", "endpoint": "/api/v3/depth",
         "cols": ["symbol", "side", "level", "price", "qty", "fetched_at"]},
    ],
    "Realtime stream": [
        {"name": "prices_intraday", "grain": "one row per symbol per minute", "endpoint": "/api/v3/klines (1m), polled",
         "cols": ["ts", "symbol", "open", "high", "low", "close", "volume", "trades"]},
    ],
}

ASSET_CLASSES = {
    "Precious metal · ทองคำ": GOLD,   # PAXG = gold-backed token
    "Crypto": CRYPTO,
    "Fiat / FX": FIAT,
}


def dir_size_mb(name: str) -> float:
    p = RAW / name
    return sum(f.stat().st_size for f in p.rglob("*.parquet")) / 1e6 if p.exists() else 0.0


UA = {"User-Agent": "bigdata-edu-project/1.0"}  # Binance blocks the default python-requests UA


def live_prices(symbols: list[str]) -> dict:
    try:
        r = requests.get(BASE + "/api/v3/ticker/price",
                         params={"symbols": json.dumps(symbols, separators=(",", ":"))},
                         headers=UA, timeout=15)
        return {d["symbol"]: float(d["price"]) for d in r.json()}
    except Exception:
        return {}


def fx_thb() -> float | None:
    try:
        r = requests.get("https://api.frankfurter.dev/v1/latest?base=USD&symbols=THB", timeout=10)
        return r.json()["rates"]["THB"]
    except Exception:
        return None


def display() -> None:
    print("=" * 70)
    print("DATA CATALOG   ·   source:", SOURCE)
    print("=" * 70)
    tot_rows = tot_mb = n = 0
    for cat, items in DATASETS.items():
        print(f"\n▌ {cat}")
        for d in items:
            rows, mb = ROWS.get(d["name"], 0), dir_size_mb(d["name"])
            tot_rows += rows; tot_mb += mb; n += 1
            print(f"  {d['name']:16}{rows:>13,} rows{mb:>8.1f} MB")
            print(f"      grain   : {d['grain']}")
            print(f"      from    : {d['endpoint']}")
            print(f"      columns : {', '.join(d['cols'])}")
    print(f"\n  {'TOTAL':16}{tot_rows:>13,} rows{tot_mb:>8.1f} MB   across {n} datasets")

    syms = sum(ASSET_CLASSES.values(), [])
    px, fx = live_prices(syms), fx_thb()
    print("\n" + "=" * 70)
    print("ASSET CATALOG   ·   live snapshot" + (f"   ·   ฿{fx:.2f}/$1" if fx else ""))
    print("=" * 70)
    for cls, members in ASSET_CLASSES.items():
        print(f"\n▌ {cls}  ({len(members)})")
        for s in members:
            p = px.get(s)
            if p is None:
                print(f"  {s:10}  (no live quote)")
            elif fx:
                print(f"  {s:10}  ฿{p * fx:>16,.2f}")
            else:
                print(f"  {s:10}  ${p:>16,.2f}")


def write_md() -> None:
    lines = ["# Data catalog", "", f"**Source:** {SOURCE}", ""]
    lines += ["## Datasets by category", ""]
    for cat, items in DATASETS.items():
        lines.append(f"### {cat}")
        lines.append("")
        lines.append("| Dataset | Rows | Grain | From | Columns |")
        lines.append("|---|--:|---|---|---|")
        for d in items:
            lines.append(f"| `{d['name']}` | {ROWS.get(d['name'],0):,} | {d['grain']} | "
                         f"`{d['endpoint']}` | {', '.join('`'+c+'`' for c in d['cols'])} |")
        lines.append("")
    lines += ["## Assets by class", ""]
    for cls, members in ASSET_CLASSES.items():
        lines.append(f"- **{cls}** ({len(members)}): {', '.join(members)}")
    lines.append("")
    Path("CATALOG.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote CATALOG.md")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--md", action="store_true", help="also write CATALOG.md")
    a = p.parse_args()
    display()
    if a.md:
        write_md()
