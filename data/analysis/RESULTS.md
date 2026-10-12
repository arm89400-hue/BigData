# Analysis results

Generated from `data/raw/` by `analysis/analyze.py`. Hourly big-data pass processed **13,795,748 rows** across **506 USDT pairs**.

## Headline figures (daily series)

| Asset | Ann. return | Ann. volatility | Max drawdown | History |
|---|--:|--:|--:|--:|
| BNB (BNBUSDT) | 99.5% | 93.4% | -80.0% | 3262d |
| Solana (SOLUSDT) | 76.9% | 113.4% | -96.3% | 2253d |
| ETH/EUR (ETHEUR) | 54.3% | 80.0% | -77.1% | 2474d |
| Dogecoin (DOGEUSDT) | 53.4% | 125.3% | -92.3% | 2656d |
| Chainlink (LINKUSDT) | 53.3% | 106.7% | -90.2% | 2826d |
| BTC/EUR (BTCEUR) | 43.1% | 59.6% | -73.6% | 2474d |
| Bitcoin (BTCUSDT) | 38.3% | 67.4% | -83.2% | 3343d |
| Ethereum (ETHUSDT) | 26.2% | 87.2% | -94.0% | 3343d |
| TRON (TRXUSDT) | 26.0% | 84.7% | -83.1% | 3045d |
| Gold (PAXGUSDT) | 13.1% | 18.7% | -28.1% | 2236d |
| XRP (XRPUSDT) | 5.6% | 97.5% | -85.0% | 3083d |
| Cardano (ADAUSDT) | 0.4% | 98.8% | -95.2% | 3100d |
| Euro (EURUSDT) | 0.1% | 8.7% | -23.8% | 2474d |
| Pound (GBPUSDT) | -1.9% | 12.2% | -27.9% | 1257d |
| Litecoin (LTCUSDT) | -15.6% | 91.3% | -93.4% | 3225d |

## Key findings

- **Gold (PAXG)** returned **13.1%/yr** with only **18.7%** volatility and a **-28.1%** worst drawdown — far calmer than crypto.
- **Bitcoin** returned **38.3%/yr** at **67.4%** volatility (drawdown -83.2%).
- **Gold vs Bitcoin** daily-return correlation is **0.15** — weakly related, so gold is a genuine diversifier.
- Most volatile asset studied: **Dogecoin** (125.3%); calmest: **Euro** (8.7%).
- By traded value over the hourly set, the top pair is **BTCUSDT** ($5777.69B across 80,106 bars).

## Output files

- `data/analysis/asset_performance.csv`
- `data/analysis/return_correlation.csv`
- `data/analysis/hourly_market_scale.csv`

_Education project; not investment advice._
