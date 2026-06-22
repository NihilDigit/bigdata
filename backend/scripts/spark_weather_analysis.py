#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

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


def main() -> int:
    args = parse_args()
    local_output = Path(args.local_output)

    builder = (
        SparkSession.builder.appName("weather-lab-analysis")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
    )
    if args.source == "hive":
        builder = builder.enableHiveSupport()
    spark = builder.getOrCreate()

    try:
        weather = parse_collect_ts(read_weather(spark, args)).withColumn(
            "collect_date", F.to_date("collect_ts")
        )

        station_summary = (
            weather.groupBy("station_id", "station_name")
            .agg(
                F.count("*").alias("records"),
                F.round(F.avg("temperature"), 2).alias("avg_temperature"),
                F.round(F.min("temperature"), 2).alias("min_temperature"),
                F.round(F.max("temperature"), 2).alias("max_temperature"),
                F.round(F.avg("humidity"), 2).alias("avg_humidity"),
                F.round(F.avg("pressure"), 2).alias("avg_pressure"),
                F.round(F.avg("wind_speed"), 2).alias("avg_wind_speed"),
            )
            .orderBy("station_id")
        )

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

        write_json(
            local_output / "station_summary.json",
            [row_to_dict(row) for row in station_summary.collect()],
        )
        write_json(
            local_output / "daily_summary.json",
            [row_to_dict(row) for row in daily_summary.collect()],
        )
        write_json(
            local_output / "hourly_series.json",
            [row_to_dict(row) for row in window_mean.collect()],
        )

        print(f"source={args.source}")
        print(f"input={args.hive_table if args.source == 'hive' else args.input_path}")
        print(f"hdfs_output={args.hdfs_output}")
        if not args.no_compat_output:
            print(f"compat_output={args.compat_output}")
        print(f"local_output={local_output.resolve()}")
        print(f"window_seconds={args.window_seconds}")
        print(f"records={weather.count()}")
        station_summary.show(truncate=False)
        daily_summary.show(9, truncate=False)
    finally:
        spark.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
