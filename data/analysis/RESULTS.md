# Analysis results

Generated from `data/raw/` by `analysis/analyze.py`. Hourly big-data pass processed **13,805,362 rows** across **506 USDT pairs**.

## Headline figures (daily series)

| Asset | Ann. return | Ann. volatility | Max drawdown | History |
|---|--:|--:|--:|--:|
| BNB (BNBUSDT) | 98.6% | 93.4% | -80.0% | 3263d |
| Solana (SOLUSDT) | 74.6% | 113.4% | -96.3% | 2254d |
| ETH/EUR (ETHEUR) | 53.2% | 80.0% | -77.1% | 2475d |
| Dogecoin (DOGEUSDT) | 51.9% | 125.3% | -92.3% | 2657d |
| Chainlink (LINKUSDT) | 51.7% | 106.7% | -90.2% | 2827d |
| BTC/EUR (BTCEUR) | 42.6% | 59.6% | -73.6% | 2475d |
| Bitcoin (BTCUSDT) | 37.9% | 67.4% | -83.2% | 3344d |
| TRON (TRXUSDT) | 25.8% | 84.7% | -83.1% | 3046d |
| Ethereum (ETHUSDT) | 25.5% | 87.2% | -94.0% | 3344d |
| Gold (PAXGUSDT) | 12.9% | 18.7% | -28.1% | 2237d |
| XRP (XRPUSDT) | 4.8% | 97.5% | -85.0% | 3084d |
| Euro (EURUSDT) | 0.0% | 8.7% | -23.8% | 2475d |
| Cardano (ADAUSDT) | -0.8% | 98.8% | -95.2% | 3101d |
| Pound (GBPUSDT) | -1.9% | 12.2% | -27.9% | 1257d |
| Litecoin (LTCUSDT) | -16.4% | 91.3% | -93.4% | 3226d |

## Key findings

- **Gold (PAXG)** returned **12.9%/yr** with only **18.7%** volatility and a **-28.1%** worst drawdown — far calmer than crypto.
- **Bitcoin** returned **37.9%/yr** at **67.4%** volatility (drawdown -83.2%).
- **Gold vs Bitcoin** daily-return correlation is **0.15** — weakly related, so gold is a genuine diversifier.
- Most volatile asset studied: **Dogecoin** (125.3%); calmest: **Euro** (8.7%).
- By traded value over the hourly set, the top pair is **BTCUSDT** ($5778.67B across 80,125 bars).

## Output files

- `data/analysis/asset_performance.csv`
- `data/analysis/return_correlation.csv`
- `data/analysis/hourly_market_scale.csv`

_Education project; not investment advice._
