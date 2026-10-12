"""Analysis layer (runs on this machine, no Spark/JVM needed).

Turns data/raw/ into report-ready results in data/analysis/:
  - asset_performance.csv   per-asset return, volatility, drawdown (daily series)
  - return_correlation.csv  correlation of daily returns (is gold correlated with crypto?)
  - hourly_market_scale.csv per-pair bars / traded value over the full hourly set (big-data pass)
  - RESULTS.md              a written summary with the actual numbers

The hourly set (~13.8M rows) is aggregated one partition file at a time, so this never loads
the whole thing into memory. The equivalent Spark job is in analysis/spark_analysis.py.
"""
import math

import numpy as np
import pandas as pd

from ingest.common import RAW, read_dataset

ANALYSIS = RAW.parent / "analysis"
YEAR = 365  # crypto trades every day, so annualise over 365, not 252

NAMES = {"PAXGUSDT": "Gold", "BTCUSDT": "Bitcoin", "ETHUSDT": "Ethereum", "BNBUSDT": "BNB",
         "SOLUSDT": "Solana", "XRPUSDT": "XRP", "ADAUSDT": "Cardano", "DOGEUSDT": "Dogecoin",
         "TRXUSDT": "TRON", "LTCUSDT": "Litecoin", "LINKUSDT": "Chainlink",
         "EURUSDT": "Euro", "GBPUSDT": "Pound", "BTCEUR": "BTC/EUR", "ETHEUR": "ETH/EUR"}


def daily_metrics() -> pd.DataFrame:
    df = read_dataset(RAW / "prices_daily")[["symbol", "date", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])
    rows = []
    for sym, g in df.groupby("symbol"):
        g = g.dropna(subset=["close"])
        if len(g) < 30:
            continue
        close = g["close"].to_numpy()
        ret = np.diff(np.log(close))
        days = (g["date"].iloc[-1] - g["date"].iloc[0]).days or 1
        total_ret = close[-1] / close[0] - 1
        ann_ret = (close[-1] / close[0]) ** (YEAR / days) - 1
        ann_vol = ret.std(ddof=1) * math.sqrt(YEAR)
        peak = np.maximum.accumulate(close)
        max_dd = (close / peak - 1).min()
        rows.append({
            "symbol": sym, "name": NAMES.get(sym, sym),
            "start": g["date"].iloc[0].date(), "end": g["date"].iloc[-1].date(),
            "days": days, "last_close": round(float(close[-1]), 4),
            "total_return_pct": round(total_ret * 100, 1),
            "ann_return_pct": round(ann_ret * 100, 1),
            "ann_volatility_pct": round(ann_vol * 100, 1),
            "return_vol_ratio": round(ann_ret / ann_vol, 2) if ann_vol else None,
            "max_drawdown_pct": round(max_dd * 100, 1),
        })
    return pd.DataFrame(rows).sort_values("ann_return_pct", ascending=False)


def return_correlation() -> pd.DataFrame:
    df = read_dataset(RAW / "prices_daily")[["symbol", "date", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    keep = [s for s in NAMES if s in set(df["symbol"])]
    wide = (df[df["symbol"].isin(keep)]
            .pivot_table(index="date", columns="symbol", values="close")
            .sort_index())
    rets = np.log(wide / wide.shift(1)).dropna(how="all")
    corr = rets.corr()
    corr = corr.reindex(index=keep, columns=keep)
    corr.index = [NAMES.get(s, s) for s in corr.index]
    corr.columns = [NAMES.get(s, s) for s in corr.columns]
    return corr.round(3)


def hourly_scale() -> tuple[pd.DataFrame, int]:
    """Memory-safe pass over the full hourly set: per-pair bars, trades, traded value."""
    files = sorted((RAW / "prices_1h").rglob("*.parquet"))
    acc, total = [], 0
    for f in files:
        part = pd.read_parquet(f, columns=["symbol", "quote_volume", "trades"])
        total += len(part)
        acc.append(part.groupby("symbol").agg(bars=("trades", "size"),
                                              trades=("trades", "sum"),
                                              quote_volume=("quote_volume", "sum")))
    agg = (pd.concat(acc).groupby("symbol").sum()
           .sort_values("quote_volume", ascending=False).reset_index())
    agg["quote_volume_bn"] = (agg["quote_volume"] / 1e9).round(2)
    return agg, total


def write_results(perf, corr, scale, total_bars):
    gold = perf[perf.symbol == "PAXGUSDT"].squeeze()
    btc = perf[perf.symbol == "BTCUSDT"].squeeze()
    cname = {v: k for k, v in NAMES.items()}
    gb_corr = corr.loc["Gold", "Bitcoin"] if "Gold" in corr.index and "Bitcoin" in corr.columns else float("nan")
    most_vol = perf.sort_values("ann_volatility_pct", ascending=False).iloc[0]
    least_vol = perf.sort_values("ann_volatility_pct").iloc[0]
    lines = [
        "# Analysis results", "",
        f"Generated from `data/raw/` by `analysis/analyze.py`. "
        f"Hourly big-data pass processed **{total_bars:,} rows** across "
        f"**{len(scale)} USDT pairs**.", "",
        "## Headline figures (daily series)", "",
        "| Asset | Ann. return | Ann. volatility | Max drawdown | History |",
        "|---|--:|--:|--:|--:|",
    ]
    for _, r in perf.iterrows():
        lines.append(f"| {r['name']} ({r['symbol']}) | {r['ann_return_pct']}% | "
                     f"{r['ann_volatility_pct']}% | {r['max_drawdown_pct']}% | {r['days']}d |")
    lines += [
        "", "## Key findings", "",
        f"- **Gold (PAXG)** returned **{gold['ann_return_pct']}%/yr** with only "
        f"**{gold['ann_volatility_pct']}%** volatility and a **{gold['max_drawdown_pct']}%** worst drawdown "
        f"— far calmer than crypto.",
        f"- **Bitcoin** returned **{btc['ann_return_pct']}%/yr** at **{btc['ann_volatility_pct']}%** "
        f"volatility (drawdown {btc['max_drawdown_pct']}%).",
        f"- **Gold vs Bitcoin** daily-return correlation is **{gb_corr:.2f}** — "
        f"{'weakly' if abs(gb_corr) < 0.3 else 'moderately'} related, so gold is a genuine diversifier.",
        f"- Most volatile asset studied: **{most_vol['name']}** ({most_vol['ann_volatility_pct']}%); "
        f"calmest: **{least_vol['name']}** ({least_vol['ann_volatility_pct']}%).",
        f"- By traded value over the hourly set, the top pair is **{scale.iloc[0]['symbol']}** "
        f"(${scale.iloc[0]['quote_volume_bn']}B across {int(scale.iloc[0]['bars']):,} bars).",
        "", "## Output files", "",
        "- `data/analysis/asset_performance.csv`",
        "- `data/analysis/return_correlation.csv`",
        "- `data/analysis/hourly_market_scale.csv`", "",
        "_Education project; not investment advice._", "",
    ]
    (ANALYSIS / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    print("[analysis] daily metrics ...")
    perf = daily_metrics()
    perf.to_csv(ANALYSIS / "asset_performance.csv", index=False)
    print("[analysis] return correlation ...")
    corr = return_correlation()
    corr.to_csv(ANALYSIS / "return_correlation.csv")
    print("[analysis] hourly big-data pass ...")
    scale, total_bars = hourly_scale()
    scale.to_csv(ANALYSIS / "hourly_market_scale.csv", index=False)
    write_results(perf, corr, scale, total_bars)

    print(f"\nprocessed {total_bars:,} hourly rows, {len(scale)} pairs")
    print("\n=== asset performance (daily) ===")
    print(perf[["name", "ann_return_pct", "ann_volatility_pct", "max_drawdown_pct"]].to_string(index=False))
    print("\n=== Gold vs Bitcoin daily-return correlation ===")
    print(round(float(corr.loc["Gold", "Bitcoin"]), 3))
    print(f"\nwrote 3 CSVs + RESULTS.md -> {ANALYSIS}")


if __name__ == "__main__":
    main()
