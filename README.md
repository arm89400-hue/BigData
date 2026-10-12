# Big Data Analytics for Money Markets (Crypto, Gold & FX) — Binance

College education project. Ingestion layer: scans market data from the **Binance public API**
(`https://api.binance.com`) into `data/raw/` as Parquet, ready for PySpark. No API key is
needed for market data. Theme: *money* — crypto, fiat currencies, and **gold**.

> **Gold:** Binance lists gold as **PAXG (PAX Gold)**, where 1 token = 1 fine troy ounce of
> real gold held in custody. So `PAXGUSDT` is effectively a USD gold-price series, sitting in
> the same dataset as the crypto and fiat pairs.

## Data sources (all from Binance)

| # | Endpoint | Job | Output (`data/raw/`) | Content |
|---|----------|-----|----------------------|---------|
| 1 | `/api/v3/exchangeInfo` | `ingest/symbols.py` | `symbols/` | Every tradable pair (~3,700): base/quote asset, status, spot/margin flags |
| 2 | `/api/v3/klines` | `ingest/prices_daily.py` | `prices_daily/year=YYYY/` | Daily OHLCV + volume/trades, full history, for the money+gold watchlist (or every USDT pair) |
| 3 | `/api/v3/ticker/24hr` | `ingest/ticker_24h.py` | `ticker_24h/` | All-market 24h snapshot: price change %, high/low, volume, trade count |
| 4 | `/api/v3/depth` | `ingest/orderbook.py` | `orderbook/` | Order-book depth snapshot (top bid/ask levels) for the watchlist |
| RT | `/api/v3/klines` (1m) | `ingest/prices_intraday.py` | `prices_intraday/date=YYYY-MM-DD/` | 1-minute bars polled live — crypto trades 24/7 |

The **money + gold watchlist** (`ingest/common.py: WATCHLIST`):
- **Gold:** `PAXGUSDT`
- **Crypto:** BTC, ETH, BNB, XRP, SOL, ADA, DOGE, TRX, LTC, LINK (all vs USDT)
- **Fiat money:** `EURUSDT`, `GBPUSDT`, `BTCEUR`, `ETHEUR`

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
# Batch: pull everything, then print row counts and sizes
.\.venv\Scripts\python.exe run_batch.py
.\.venv\Scripts\python.exe run_batch.py --only symbols prices   # selected jobs
.\.venv\Scripts\python.exe run_batch.py --all-usdt              # daily: scan EVERY USDT pair

# Single jobs
.\.venv\Scripts\python.exe -m ingest.prices_daily --symbols PAXGUSDT BTCUSDT
.\.venv\Scripts\python.exe -m ingest.prices_daily --interval 1w        # weekly candles

# Near-realtime: leave running; appends new 1-minute bars each poll
.\.venv\Scripts\python.exe -m ingest.prices_intraday                   # watchlist, every 1 min
.\.venv\Scripts\python.exe -m ingest.prices_intraday --symbols PAXGUSDT --every 5
.\.venv\Scripts\python.exe -m ingest.prices_intraday --once            # one poll, for testing
```

## Dashboard (live)

`dashboard.html` is a self-contained web page: a summary of everything in `data/raw/` plus a
**live** market board and price chart that poll Binance's public API directly in the browser.

```powershell
# Option A - just open the file
start dashboard.html

# Option B - serve it (how it was tested)
.\.venv\Scripts\python.exe -m http.server 8787 --bind 127.0.0.1
#   then open http://localhost:8787/dashboard.html
```

Currency & designs:
- **Priced in Thai Baht (฿)** — all prices, the chart, movers and the calculator are converted
  live from USD using `frankfurter.dev` (jsdelivr currency-api fallback); the rate shows in the nav.
- **Five design palettes** (Gold, Ocean, Grape, Sunset, Forest) picked from the nav dots, plus a
  light/dark toggle — your choice is remembered.

What's on the page:
- **Live market board** — watchlist prices + 24h change, refreshing every 5s.
- **Live chart with signals** — candles plus moving averages (7/25/99), Bollinger Bands, an
  RSI(14) read-out, and a least-squares **trend forecast** with a 95% band (a statistical
  projection, not advice).
- **Live risk/reward analysis** — return, volatility, drawdown and the gold-vs-Bitcoin
  correlation, recomputed in the browser from fresh daily closes (auto-refresh every 5 min).
- **"What if I invested" backtester** — $amount + asset + date → value today, total return
  and per-year return, from live Binance daily closes.
- **Across all USDT markets** — top gainers and most-traded, refreshing every 60s.

Realtime notes:
- The **scan summary** (row counts, sizes) is a *snapshot* baked into the page.
- **Everything else is realtime** while the page is open and you're online.
- A published Claude artifact can't do the live part (its sandbox blocks outbound requests),
  so the dashboard is a local file you open yourself.

## Analysis

`analysis/` turns `data/raw/` into results in `data/analysis/`.

```powershell
# Runs here now (memory-safe pandas; aggregates the 13.8M-row hourly set file-by-file)
.\.venv\Scripts\python.exe -m analysis.analyze

# The same analysis as a distributed Spark job (for a cluster / Databricks / local Spark)
spark-submit analysis/spark_analysis.py
```

Outputs: `asset_performance.csv`, `return_correlation.csv`, `hourly_market_scale.csv`, `RESULTS.md`.

Headline findings (annualised, from daily closes):

| Asset | Ann. return | Volatility | Max drawdown |
|---|--:|--:|--:|
| Gold (PAXG) | +13.1% | **18.7%** | −28.1% |
| Bitcoin | +38.3% | 67.4% | −83.2% |
| Euro | +0.1% | 8.7% | −23.8% |

- **Gold has the best return-per-risk** of any asset studied: a steady ~13%/yr for a fraction of crypto's volatility.
- **Gold vs Bitcoin daily-return correlation is just 0.15** — gold moves largely independently of crypto, so it's a genuine diversifier.
- The hourly big-data pass processed **13,795,748 rows across 506 pairs**.

## Reading the data in Spark

```python
daily = spark.read.parquet("data/raw/prices_daily")         # 'year' becomes a column
intraday = spark.read.parquet("data/raw/prices_intraday")   # 'date' becomes a column

gold = daily.filter(daily.symbol == "PAXGUSDT")             # the gold price series

# Streaming: pick up each new intraday file as it lands
stream = (spark.readStream.schema(intraday.schema)
          .parquet("data/raw/prices_intraday"))
```

## Notes and limitations

- **Market data only, no key needed.** Only account/trading endpoints need an API key; this
  project never touches them, so there are no credentials to manage.
- **Rate limits:** `ingest/common.py: get()` honours Binance's `Retry-After` header and backs
  off on HTTP 429/418, so a full `--all-usdt` scan won't get the IP banned.
- **PAXG history** starts ~Aug 2020 (when the token listed); it is a very close proxy for spot
  gold but can carry a small premium/discount vs the physical XAU price.
- **UTC everywhere.** Binance timestamps are UTC milliseconds; all dates/times are kept in UTC.
- **Education use.** Binance market data is public; this is a research/learning project, not
  trading advice.
- `pyarrow.dataset` is blocked by Windows Application Control on the dev machine, so partitions
  are written file-by-file (`ingest/common.py: write_dataset`). Spark is unaffected.
