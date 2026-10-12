# Data catalog

**Source:** Binance public API  (data-api.binance.vision / api.binance.com)

## Datasets by category

### Reference / master data

| Dataset | Rows | Grain | From | Columns |
|---|--:|---|---|---|
| `symbols` | 3,724 | one row per trading pair | `/api/v3/exchangeInfo` | `symbol`, `base_asset`, `quote_asset`, `status`, `is_spot`, `is_margin` |

### Price history (OHLCV)

| Dataset | Rows | Grain | From | Columns |
|---|--:|---|---|---|
| `prices_daily` | 41,066 | one row per symbol per day | `/api/v3/klines (1d)` | `symbol`, `date`, `open`, `high`, `low`, `close`, `volume`, `quote_volume`, `trades`, `year` |
| `prices_1h` | 13,795,748 | one row per symbol per hour | `/api/v3/klines (1h)` | `symbol`, `date`, `open`, `high`, `low`, `close`, `volume`, `quote_volume`, `trades`, `year` |

### Market snapshots

| Dataset | Rows | Grain | From | Columns |
|---|--:|---|---|---|
| `ticker_24h` | 3,727 | one row per market, point-in-time | `/api/v3/ticker/24hr` | `symbol`, `last_price`, `price_change_pct`, `high_price`, `low_price`, `volume`, `quote_volume`, `trades`, `fetched_at` |
| `orderbook` | 2,800 | one row per price level, point-in-time | `/api/v3/depth` | `symbol`, `side`, `level`, `price`, `qty`, `fetched_at` |

### Realtime stream

| Dataset | Rows | Grain | From | Columns |
|---|--:|---|---|---|
| `prices_intraday` | 238 | one row per symbol per minute | `/api/v3/klines (1m), polled` | `ts`, `symbol`, `open`, `high`, `low`, `close`, `volume`, `trades` |

## Assets by class

- **Precious metal · ทองคำ** (1): PAXGUSDT
- **Crypto** (10): BTCUSDT, ETHUSDT, BNBUSDT, XRPUSDT, SOLUSDT, ADAUSDT, DOGEUSDT, TRXUSDT, LTCUSDT, LINKUSDT
- **Fiat / FX** (4): EURUSDT, GBPUSDT, BTCEUR, ETHEUR
