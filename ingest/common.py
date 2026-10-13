"""Shared paths and helpers for all Binance ingestion jobs.

Everything is pulled from Binance's public REST API (https://api.binance.com) - market data
needs no API key. Timestamps from Binance are UTC milliseconds; we keep everything in UTC.
"""
import shutil
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
TZ = "UTC"
BASE = "https://api.binance.com"

# A "money + gold" watchlist used by the per-symbol jobs (daily/intraday klines, order book).
#   gold       : PAXGUSDT  - PAX Gold, 1 token = 1 fine troy oz of real gold
#   crypto     : the major coins by market cap
#   fiat money : EUR / GBP / fiat-quoted pairs, so the project covers currencies too
GOLD = ["PAXGUSDT"]
CRYPTO = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT", "ADAUSDT",
          "DOGEUSDT", "TRXUSDT", "LTCUSDT", "LINKUSDT"]
FIAT = ["EURUSDT", "GBPUSDT", "BTCEUR", "ETHEUR"]
WATCHLIST = GOLD + CRYPTO + FIAT


# Some Binance symbols are non-ASCII (e.g. Chinese meme coins); the Windows console/redirect
# codepage (cp874 on Thai Windows) can't encode them, so always print UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(msg: str) -> None:
    print(f"[{pd.Timestamp.now(tz=TZ):%H:%M:%S}] {msg}", flush=True)


def chunks(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def retry(fn, *args, attempts: int = 3, wait: float = 5, **kwargs):
    """Call fn, retrying with linear backoff."""
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if attempt == attempts:
                raise
            log(f"  retry {attempt}/{attempts - 1} after error: {exc}")
            time.sleep(wait * attempt)


_session = requests.Session()
_session.headers["User-Agent"] = "bigdata-edu-project/1.0"


def get(path: str, **params):
    """GET a Binance endpoint and return parsed JSON, honouring rate-limit back-off.

    On 429 (too many requests) / 418 (banned) Binance sends a Retry-After header; we wait it
    out so a full scan never trips the limit. Any other error is raised for retry() to catch.
    """
    for attempt in range(5):
        r = _session.get(f"{BASE}{path}", params=params, timeout=30)
        if r.status_code in (429, 418):
            wait = int(r.headers.get("Retry-After", 2 ** attempt))
            log(f"  rate-limited ({r.status_code}), sleeping {wait}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up on {path} after repeated rate limits")


def write_dataset(df: pd.DataFrame, name: str, partition_col: str | None = None) -> None:
    """Replace data/raw/<name>: write to a temp dir, then swap.

    Partitions are written by hand as <col>=<value>/part-0.parquet (Hive layout, which Spark
    reads natively) because pyarrow.dataset is blocked by Application Control on this machine.
    """
    target = RAW / name
    tmp = RAW / f"_{name}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    if partition_col:
        for key, part in df.groupby(partition_col):
            folder = tmp / f"{partition_col}={key}"
            folder.mkdir()
            part.drop(columns=partition_col).to_parquet(folder / "part-0.parquet", index=False)
    else:
        df.to_parquet(tmp / "part-0.parquet", index=False)
    shutil.rmtree(target, ignore_errors=True)
    tmp.rename(target)
    log(f"saved {name}: {len(df):,} rows -> {target}")


def append_partition(df: pd.DataFrame, name: str, part: str) -> None:
    """Append one file under data/raw/<name>/<part>/ without touching other partitions.

    Used by the near-realtime job, which adds a file per poll instead of rewriting the set.
    """
    folder = RAW / name / part
    folder.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now(tz=TZ).strftime("%H%M%S")
    df.to_parquet(folder / f"part-{stamp}.parquet", index=False)
    log(f"appended {name}/{part}: {len(df):,} rows")


def read_dataset(folder: Path, columns: list[str] | None = None) -> pd.DataFrame:
    """Read every parquet file under folder (pandas can't read a directory here, see above)."""
    files = sorted(folder.rglob("*.parquet"))
    if not files:
        return pd.DataFrame(columns=columns)
    return pd.concat([pd.read_parquet(f, columns=columns) for f in files], ignore_index=True)


def load_symbols(quote: str | None = None, spot_only: bool = True) -> list[str]:
    """Trading symbols from data/raw/symbols (run ingest.symbols first).

    quote='USDT' keeps only USDT-quoted pairs; spot_only drops non-spot markets.
    """
    path = RAW / "symbols"
    if not path.exists():
        raise SystemExit("data/raw/symbols not found - run: python -m ingest.symbols")
    df = read_dataset(path)
    df = df[df["status"] == "TRADING"]
    if spot_only:
        df = df[df["is_spot"]]
    if quote:
        df = df[df["quote_asset"] == quote]
    return df["symbol"].tolist()
