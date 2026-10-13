"""Builds the Power BI tables in powerbi/data/ from data/raw/ and data/analysis/.

    .venv\\Scripts\\python.exe -m powerbi.build_data

Tables (all CSV, UTF-8; the Power BI queries read them as code page 65001):
  assets.csv              one row per asset: symbol, Thai name, asset class
  prices_daily.csv        daily close/high/low/volume per asset + 200-day average
  prices_monthly.csv      month-end close, monthly % change, index (avg 2023 = 100), from Aug 2020
  asset_performance.csv   annual return, volatility, drawdown, 1-year change per asset
  correlation.csv         daily-return correlation as a long table (asset_a, asset_b, corr)
  forecast.csv            next-month % change predicted per asset (simple AR(1) model)
  forecast_backtest.csv   predicted vs actual monthly % change, last 12 months, per asset
  datasets.csv            what each dataset is, where it came from, and its row count
  hourly_scale.csv        traded value per pair from the 13.8M-row hourly pass
"""
import numpy as np
import pandas as pd

from analysis.analyze import ANALYSIS, NAMES
from ingest.common import RAW, read_dataset

OUT = RAW.parent.parent / "powerbi" / "data"

NAME_TH = {"PAXGUSDT": "ทองคำ (PAXG)", "BTCUSDT": "Bitcoin", "ETHUSDT": "Ethereum",
           "BNBUSDT": "BNB", "SOLUSDT": "Solana", "XRPUSDT": "XRP", "ADAUSDT": "Cardano",
           "DOGEUSDT": "Dogecoin", "TRXUSDT": "TRON", "LTCUSDT": "Litecoin",
           "LINKUSDT": "Chainlink", "EURUSDT": "ยูโร (EUR)", "GBPUSDT": "ปอนด์ (GBP)",
           "BTCEUR": "BTC/EUR", "ETHEUR": "ETH/EUR"}
CLASS_TH = {"PAXGUSDT": "ทองคำ", "EURUSDT": "สกุลเงิน", "GBPUSDT": "สกุลเงิน",
            "BTCEUR": "สกุลเงิน", "ETHEUR": "สกุลเงิน"}   # everything else is crypto
BASE_YEAR = 2023        # index base: average close in 2023 (พ.ศ. 2566) = 100
LOOKBACK = 36           # months of history the forecast model is fitted on
BACKTEST = 12           # months shown in the predicted-vs-actual chart
INDEX_FROM = "2020-08-01"   # gold (PAXG) history starts Aug 2020, so the index chart does too


def save(df: pd.DataFrame, name: str) -> None:
    df.to_csv(OUT / name, index=False, encoding="utf-8")
    print(f"  {name:24s} {len(df):>7,} rows")


def ar1_next(returns: np.ndarray) -> float:
    """Fit r[t+1] = a + b*r[t] by least squares and predict the next value."""
    x, y = returns[:-1], returns[1:]
    if len(x) < 6 or np.std(x) == 0:
        return float(np.mean(returns))
    b, a = np.polyfit(x, y, 1)
    return float(a + b * returns[-1])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    daily = read_dataset(RAW / "prices_daily")
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily[daily["symbol"].isin(NAME_TH)].sort_values(["symbol", "date"])
    daily["ma200"] = daily.groupby("symbol")["close"].transform(lambda s: s.rolling(200).mean())

    assets = pd.DataFrame({"symbol": list(NAME_TH)})
    assets["name_th"] = assets["symbol"].map(NAME_TH)
    assets["name_en"] = assets["symbol"].map(NAMES)
    assets["asset_class"] = assets["symbol"].map(CLASS_TH).fillna("คริปโต")
    save(assets, "assets.csv")

    save(daily[["date", "symbol", "open", "high", "low", "close", "ma200",
                "volume", "quote_volume", "trades"]].round(6), "prices_daily.csv")

    # month-end closes; the current month is still running, so it is dropped
    monthly = (daily.set_index("date").groupby("symbol")["close"].resample("ME").last()
               .dropna().reset_index())
    this_month = daily["date"].max().to_period("M").to_timestamp("M")
    monthly = monthly[monthly["date"] < this_month]
    monthly["change_pct"] = monthly.groupby("symbol")["close"].pct_change() * 100
    base = (daily[daily["date"].dt.year == BASE_YEAR].groupby("symbol")["close"].mean())
    monthly["index_2566"] = monthly["close"] / monthly["symbol"].map(base) * 100
    monthly = monthly.rename(columns={"date": "month"})
    save(monthly[monthly["month"] >= INDEX_FROM].round(4), "prices_monthly.csv")

    perf = pd.read_csv(ANALYSIS / "asset_performance.csv")
    last = daily.groupby("symbol").last()
    year_ago = (daily[daily["date"] <= daily["date"].max() - pd.Timedelta(days=365)]
                .groupby("symbol")["close"].last())
    perf["close_1y_ago"] = perf["symbol"].map(year_ago)
    perf["close_latest"] = perf["symbol"].map(last["close"])
    perf["change_1y_pct"] = (perf["close_latest"] / perf["close_1y_ago"] - 1) * 100
    perf["latest_date"] = perf["symbol"].map(last["date"]).dt.date
    save(perf.round(4), "asset_performance.csv")

    corr = pd.read_csv(ANALYSIS / "return_correlation.csv", index_col=0)
    corr = corr.stack().reset_index()
    corr.columns = ["asset_a", "asset_b", "corr"]
    save(corr, "correlation.csv")

    # Forecast: a simple AR(1) on monthly % change, refitted each month on the last 36 months.
    # The back-test refits at every month so each prediction only uses data before it.
    preds, tests = [], []
    target = this_month.to_period("M").to_timestamp().date()   # first day of the month predicted
    for sym, g in monthly.dropna(subset=["change_pct"]).groupby("symbol"):
        r = g["change_pct"].to_numpy()
        months = g["month"].to_numpy()
        preds.append({"symbol": sym, "target_month": target,
                      "predicted_pct": ar1_next(r[-LOOKBACK:])})
        for i in range(max(len(r) - BACKTEST, LOOKBACK // 2), len(r)):
            tests.append({"symbol": sym, "month": months[i],
                          "predicted_pct": ar1_next(r[max(0, i - LOOKBACK):i]),
                          "actual_pct": r[i]})
    save(pd.DataFrame(preds).round(3), "forecast.csv")
    save(pd.DataFrame(tests).round(3), "forecast_backtest.csv")

    rows = {n: len(read_dataset(RAW / n)) for n in
            ["symbols", "ticker_24h", "orderbook", "prices_intraday", "prices_daily"]}
    hourly = pd.read_csv(ANALYSIS / "hourly_market_scale.csv")
    datasets = pd.DataFrame([
        ("ราคาซื้อขายรายชั่วโมง ทุกคู่เทียบ USDT", int(hourly["bars"].sum()), len(hourly)),
        ("ราคารายวัน: ทองคำ คริปโต สกุลเงิน", rows["prices_daily"], 15),
        ("รายชื่อคู่เทรด", rows["symbols"], None),
        ("สรุปราคาตลาด 24 ชั่วโมง", rows["ticker_24h"], None),
        ("คำสั่งซื้อขาย (order book)", rows["orderbook"], 15),
        ("ราคาทุก 1 นาที (realtime)", rows["prices_intraday"], 15),
    ], columns=["dataset_th", "rows", "pairs"])
    datasets["pairs"] = datasets["pairs"].astype("Int64")
    datasets["source"] = "Binance"
    save(datasets, "datasets.csv")
    save(hourly, "hourly_scale.csv")


if __name__ == "__main__":
    main()
