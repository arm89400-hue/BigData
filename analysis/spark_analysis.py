"""Analysis layer - PySpark version (for a real Spark cluster / Databricks / local Spark).

Same results as analysis/analyze.py, but expressed as distributed Spark DataFrame operations,
so it scales to the full hourly set (and far beyond) across a cluster.

Run:  spark-submit analysis/spark_analysis.py
      # or inside a Spark session: exec(open('analysis/spark_analysis.py').read())

Reads data/raw/prices_daily and data/raw/prices_1h (Hive-partitioned Parquet).
Writes results under data/analysis/spark/.
"""
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

YEAR = 365.0
WATCH = ["PAXGUSDT", "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
         "DOGEUSDT", "TRXUSDT", "LTCUSDT", "LINKUSDT", "EURUSDT", "GBPUSDT", "BTCEUR", "ETHEUR"]


def main():
    spark = (SparkSession.builder.appName("binance-market-analysis")
             .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    out = "data/analysis/spark"

    daily = spark.read.parquet("data/raw/prices_daily").select("symbol", "date", "close")

    # --- per-symbol daily log returns via a window ordered by date ---
    w = Window.partitionBy("symbol").orderBy("date")
    rets = (daily.withColumn("prev", F.lag("close").over(w))
                 .withColumn("logret", F.log(F.col("close") / F.col("prev")))
                 .where(F.col("prev").isNotNull()))

    # --- performance: return, annualised volatility, drawdown ---
    peak = daily.withColumn("peak", F.max("close").over(w.rowsBetween(Window.unboundedPreceding, 0)))
    dd = peak.groupBy("symbol").agg((F.min(F.col("close") / F.col("peak")) - 1).alias("max_drawdown"))
    span = daily.groupBy("symbol").agg(
        F.first("close").alias("first_close"), F.last("close").alias("last_close"),
        F.datediff(F.max("date"), F.min("date")).alias("days"),
        F.min("date").alias("start"), F.max("date").alias("end"))
    vol = rets.groupBy("symbol").agg(F.stddev("logret").alias("dstd"), F.count("*").alias("n"))

    perf = (span.join(vol, "symbol").join(dd, "symbol")
            .withColumn("total_return_pct", (F.col("last_close") / F.col("first_close") - 1) * 100)
            .withColumn("ann_return_pct",
                        (F.pow(F.col("last_close") / F.col("first_close"), YEAR / F.col("days")) - 1) * 100)
            .withColumn("ann_volatility_pct", F.col("dstd") * F.sqrt(F.lit(YEAR)) * 100)
            .withColumn("max_drawdown_pct", F.col("max_drawdown") * 100)
            .where(F.col("n") >= 30)
            .orderBy(F.desc("ann_return_pct")))
    perf.coalesce(1).write.mode("overwrite").option("header", True).csv(f"{out}/asset_performance")

    # --- correlation of daily returns, gold vs the majors ---
    wl = rets.where(F.col("symbol").isin(WATCH))
    pairs = (wl.alias("a").join(wl.alias("b"), ["date"])
             .where(F.col("a.symbol") < F.col("b.symbol"))
             .groupBy(F.col("a.symbol").alias("sym_a"), F.col("b.symbol").alias("sym_b"))
             .agg(F.corr("a.logret", "b.logret").alias("corr"))
             .orderBy("sym_a", "sym_b"))
    pairs.coalesce(1).write.mode("overwrite").option("header", True).csv(f"{out}/return_correlation")

    # --- big-data pass: aggregate the full hourly set per pair ---
    hourly = spark.read.parquet("data/raw/prices_1h")
    scale = (hourly.groupBy("symbol").agg(
        F.count("*").alias("bars"), F.sum("trades").alias("trades"),
        F.sum("quote_volume").alias("quote_volume"))
        .withColumn("quote_volume_bn", F.round(F.col("quote_volume") / 1e9, 2))
        .orderBy(F.desc("quote_volume")))
    scale.coalesce(1).write.mode("overwrite").option("header", True).csv(f"{out}/hourly_market_scale")

    total = hourly.count()
    gb = pairs.where((F.col("sym_a") == "BTCUSDT") & (F.col("sym_b") == "PAXGUSDT")).collect()
    print(f"\nprocessed {total:,} hourly rows across {scale.count()} pairs")
    if gb:
        print(f"Gold vs Bitcoin daily-return correlation = {gb[0]['corr']:.3f}")
    perf.select("symbol", "ann_return_pct", "ann_volatility_pct", "max_drawdown_pct").show(20, False)
    spark.stop()


if __name__ == "__main__":
    main()
