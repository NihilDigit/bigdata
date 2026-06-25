#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T


SCHEMA = T.StructType(
    [
        T.StructField("collect_time", T.StringType(), False),
        T.StructField("station_id", T.StringType(), False),
        T.StructField("station_name", T.StringType(), False),
        T.StructField("temperature", T.DoubleType(), True),
        T.StructField("humidity", T.DoubleType(), True),
        T.StructField("pressure", T.DoubleType(), True),
        T.StructField("wind_speed", T.DoubleType(), True),
        T.StructField("wind_direction", T.DoubleType(), True),
        T.StructField("weather_code", T.IntegerType(), True),
    ]
)


def row_to_dict(row: Any) -> dict[str, Any]:
    result = row.asDict(recursive=True)
    for key, value in list(result.items()):
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()
    return result


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path", nargs="?", default="/weathertextdb")
    parser.add_argument("hdfs_output", nargs="?", default="/weather_analysis")
    parser.add_argument("local_output", nargs="?", default="data/processed")
    parser.add_argument("--source", choices=["csv", "hive"], default="csv")
    parser.add_argument("--hive-table", default="weather_table")
    parser.add_argument("--window-seconds", type=int, default=10)
    parser.add_argument("--compat-output", default="/weather_10secmean")
    parser.add_argument("--no-compat-output", action="store_true")
    return parser.parse_args()


def parse_collect_ts(weather: Any) -> Any:
    return weather.withColumn(
        "collect_ts",
        F.coalesce(
            F.to_timestamp("collect_time", "yyyy-MM-dd'T'HH:mm:ssXXX"),
            F.to_timestamp("collect_time", "yyyy-MM-dd'T'HH:mm"),
            F.to_timestamp("collect_time", "yyyy-MM-dd HH:mm:ss.SSSSSS"),
            F.to_timestamp("collect_time", "yyyy-MM-dd HH:mm:ss"),
        ),
    )


def read_weather(spark: SparkSession, args: argparse.Namespace) -> Any:
    if args.source == "hive":
        return spark.table(args.hive_table)
    return spark.read.schema(SCHEMA).option("header", "false").csv(args.input_path)


def build_spark_session(args: argparse.Namespace) -> SparkSession:
    builder = (
        SparkSession.builder.appName("weather-lab-analysis")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
    )
    if args.source == "hive":
        builder = builder.enableHiveSupport()
    return builder.getOrCreate()


def run_analysis(
    spark: SparkSession,
    args: argparse.Namespace,
    progress: Callable[[str, int], None] | None = None,
) -> dict[str, Any]:
    local_output = Path(args.local_output)

    def mark(label: str, percent: int) -> None:
        if progress:
            progress(label, percent)

    mark("读取 HDFS 气象数据", 10)
    weather = (
        parse_collect_ts(read_weather(spark, args))
        .withColumn("collect_date", F.to_date("collect_ts"))
        .withColumn("wind_direction_rad", F.radians("wind_direction"))
    )
    record_count = weather.count()
    mark(f"读取完成 records={record_count}", 25)

    mark("计算站点统计摘要", 35)
    station_summary_raw = (
        weather.groupBy("station_id", "station_name")
        .agg(
            F.count("*").alias("records"),
            F.round(F.avg("temperature"), 2).alias("avg_temperature"),
            F.round(F.min("temperature"), 2).alias("min_temperature"),
            F.round(F.max("temperature"), 2).alias("max_temperature"),
            F.round(F.avg("humidity"), 2).alias("avg_humidity"),
            F.round(F.avg("pressure"), 2).alias("avg_pressure"),
            F.round(F.avg("wind_speed"), 2).alias("avg_wind_speed"),
            F.round(F.max("pressure") - F.min("pressure"), 2).alias("pressure_delta"),
            F.round(F.max("wind_speed"), 2).alias("max_wind_speed"),
            F.avg(F.sin("wind_direction_rad")).alias("avg_wind_sin"),
            F.avg(F.cos("wind_direction_rad")).alias("avg_wind_cos"),
        )
    )
    station_summary = (
        station_summary_raw.withColumn(
            "dominant_wind_direction",
            F.round(
                F.pmod(
                    F.degrees(F.atan2(F.col("avg_wind_sin"), F.col("avg_wind_cos"))) + F.lit(360),
                    F.lit(360),
                ),
                2,
            ),
        )
        .drop("avg_wind_sin", "avg_wind_cos")
        .orderBy("station_id")
    )

    mark("计算日统计与窗口均值", 55)
    daily_summary = (
        weather.groupBy("station_id", "station_name", "collect_date")
        .agg(
            F.count("*").alias("records"),
            F.round(F.avg("temperature"), 2).alias("avg_temperature"),
            F.round(F.avg("humidity"), 2).alias("avg_humidity"),
            F.round(F.max("temperature"), 2).alias("max_temperature"),
            F.round(F.min("temperature"), 2).alias("min_temperature"),
        )
        .orderBy("collect_date", "station_id")
    )

    window_mean = (
        weather.where(F.col("collect_ts").isNotNull())
        .groupBy(
            "station_id",
            "station_name",
            F.window("collect_ts", f"{args.window_seconds} seconds").alias("time_window"),
        )
        .agg(
            F.round(F.avg("temperature"), 2).alias("temperature"),
            F.round(F.avg("humidity"), 2).alias("humidity"),
            F.round(F.avg("pressure"), 2).alias("pressure"),
            F.round(F.avg("wind_speed"), 2).alias("wind_speed"),
            F.round(F.avg("wind_direction"), 2).alias("wind_direction"),
            F.round(F.avg("weather_code")).cast("int").alias("weather_code"),
        )
        .select(
            F.date_format(F.col("time_window.start"), "yyyy-MM-dd'T'HH:mm:ss").alias(
                "collect_time"
            ),
            "station_id",
            "station_name",
            "temperature",
            "humidity",
            "pressure",
            "wind_speed",
            "wind_direction",
            "weather_code",
        )
        .orderBy("collect_time", "station_id")
    )

    mark("写入 HDFS 分析结果", 70)
    station_summary.write.mode("overwrite").option("header", "true").csv(
        f"{args.hdfs_output}/summary"
    )
    daily_summary.write.mode("overwrite").option("header", "true").csv(
        f"{args.hdfs_output}/daily_summary"
    )
    window_mean.write.mode("overwrite").option("header", "true").csv(
        f"{args.hdfs_output}/window_mean"
    )
    if not args.no_compat_output:
        window_mean.select(
            "collect_time",
            "station_name",
            "temperature",
            "humidity",
            "pressure",
            "wind_speed",
            "wind_direction",
        ).write.mode("overwrite").option("header", "true").csv(args.compat_output)

    mark("写入本地 JSON 缓存", 85)
    station_summary_rows = [row_to_dict(row) for row in station_summary.collect()]
    daily_summary_rows = [row_to_dict(row) for row in daily_summary.collect()]
    window_mean_rows = [row_to_dict(row) for row in window_mean.collect()]
    write_json(local_output / "station_summary.json", station_summary_rows)
    write_json(local_output / "daily_summary.json", daily_summary_rows)
    write_json(local_output / "hourly_series.json", window_mean_rows)

    mark("输出 Spark 汇总", 95)
    print(f"source={args.source}")
    print(f"input={args.hive_table if args.source == 'hive' else args.input_path}")
    print(f"hdfs_output={args.hdfs_output}")
    if not args.no_compat_output:
        print(f"compat_output={args.compat_output}")
    print(f"local_output={local_output.resolve()}")
    print(f"window_seconds={args.window_seconds}")
    print(f"records={record_count}")
    station_summary.show(truncate=False)
    daily_summary.show(9, truncate=False)
    mark("Spark 重算完成", 100)
    return {
        "records": record_count,
        "station_summary_rows": len(station_summary_rows),
        "daily_summary_rows": len(daily_summary_rows),
        "window_mean_rows": len(window_mean_rows),
        "hdfs_output": args.hdfs_output,
        "compat_output": None if args.no_compat_output else args.compat_output,
        "local_output": str(local_output.resolve()),
    }


def main() -> int:
    args = parse_args()
    spark = build_spark_session(args)
    try:
        run_analysis(spark, args)
    finally:
        spark.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
