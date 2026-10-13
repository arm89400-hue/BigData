"""Gold Market data pipeline, orchestrated by Airflow.

gold_market_daily (every day 08:00 Bangkok)
    symbols -> [daily prices, 24h snapshot, order book] -> analysis -> catalog
    Refreshes the Binance scan, then rebuilds data/analysis/ and CATALOG.md.

gold_market_full_scan (manual trigger only)
    symbols -> 24h snapshot -> hourly prices for every USDT pair -> analysis -> catalog
    The heavy ~13.8M-row hourly scan; takes a while, so it only runs when you start it.

Tasks call the project's own code (ingest/, analysis/, catalog.py), mounted at PROJECT_DIR.
"""
import os
import subprocess
import sys
from datetime import datetime, timedelta

from airflow.sdk import dag, task

PROJECT = os.environ.get("PROJECT_DIR", "/opt/airflow/project")
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

DEFAULTS = {"retries": 2, "retry_delay": timedelta(minutes=5)}
ONE_AT_A_TIME = 1   # runs write the same datasets, so never let two overlap


# ---- shared tasks -------------------------------------------------------------------------
@task
def symbols():
    from ingest import symbols as job
    job.main()


@task
def ticker_24h():
    from ingest import ticker_24h as job
    job.main()


@task
def analysis():
    from analysis import analyze
    analyze.main()


@task
def catalog():
    # catalog.py writes CATALOG.md relative to the working directory
    subprocess.run([sys.executable, "catalog.py", "--md"], cwd=PROJECT, check=True)


# ---- daily refresh ------------------------------------------------------------------------
@dag(dag_id="gold_market_daily", schedule="0 8 * * *", start_date=datetime(2026, 10, 1),
     catchup=False, max_active_runs=ONE_AT_A_TIME, default_args=DEFAULTS, tags=["gold-market"], doc_md=__doc__)
def gold_market_daily():
    @task
    def prices_daily():
        from ingest import prices_daily as job
        job.main()

    @task
    def orderbook():
        from ingest import orderbook as job
        job.main()

    snapshot = [prices_daily(), ticker_24h(), orderbook()]
    symbols() >> snapshot >> analysis() >> catalog()


# ---- full hourly scan (manual) ------------------------------------------------------------
@dag(dag_id="gold_market_full_scan", schedule=None, start_date=datetime(2026, 10, 1),
     catchup=False, max_active_runs=ONE_AT_A_TIME, default_args=DEFAULTS, tags=["gold-market"], doc_md=__doc__)
def gold_market_full_scan():
    @task(execution_timeout=timedelta(hours=2))
    def prices_hourly():
        from ingest import prices_hourly as job
        job.main()

    symbols() >> ticker_24h() >> prices_hourly() >> analysis() >> catalog()


gold_market_daily()
gold_market_full_scan()
