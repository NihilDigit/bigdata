#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
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


def main() -> int:
    input_path = sys.argv[1] if len(sys.argv) > 1 else "/weathertextdb"
    hdfs_output = sys.argv[2] if len(sys.argv) > 2 else "/weather_analysis"
    local_output = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("data/processed")

    spark = (
        SparkSession.builder.appName("weather-lab-analysis")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .getOrCreate()
    )

    try:
        weather = (
            spark.read.schema(SCHEMA)
            .option("header", "false")
            .csv(input_path)
            .withColumn("collect_ts", F.to_timestamp("collect_time", "yyyy-MM-dd'T'HH:mm"))
            .withColumn("collect_date", F.to_date("collect_ts"))
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

        hourly_series = weather.select(
            "collect_time",
            "station_id",
            "station_name",
            "temperature",
            "humidity",
            "pressure",
            "wind_speed",
            "wind_direction",
            "weather_code",
        ).orderBy("collect_time", "station_id")

        station_summary.write.mode("overwrite").option("header", "true").csv(
            f"{hdfs_output}/summary"
        )
        daily_summary.write.mode("overwrite").option("header", "true").csv(
            f"{hdfs_output}/daily_summary"
        )
        hourly_series.write.mode("overwrite").option("header", "true").csv(
            f"{hdfs_output}/window_mean"
        )

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
            [row_to_dict(row) for row in hourly_series.collect()],
        )

        print(f"input={input_path}")
        print(f"hdfs_output={hdfs_output}")
        print(f"local_output={local_output.resolve()}")
        print(f"records={weather.count()}")
        station_summary.show(truncate=False)
        daily_summary.show(9, truncate=False)
    finally:
        spark.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
