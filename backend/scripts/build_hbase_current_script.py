#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
from pathlib import Path


TABLE = "weather_current"


def quote(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> int:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/current_weather_combined.csv")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/processed/hbase_current_weather_puts.hbase")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    lines = [
        f"table_name = {quote(TABLE)}",
        "create table_name, 'info', 'metrics' unless exists(table_name)",
    ]

    for row in rows:
        row_key = row["id"]
        info_fields = ["name", "latitude", "longitude", "source", "time"]
        metric_fields = [
            "temperature",
            "humidity",
            "pressure",
            "wind_speed",
            "wind_direction",
            "weather_code",
        ]
        for field in info_fields:
            lines.append(
                f"put table_name, {quote(row_key)}, {quote('info:' + field)}, {quote(row[field])}"
            )
        for field in metric_fields:
            lines.append(
                f"put table_name, {quote(row_key)}, {quote('metrics:' + field)}, {quote(row[field])}"
            )

    lines.extend(
        [
            "scan table_name, {LIMIT => 10}",
            "exit",
        ]
    )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"table={TABLE} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
