#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path


RAW_DIR = Path("data/raw")


def read_latest_esp32(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"no ESP32 samples in {path}")
    return rows[-1]


def read_latest_tangshan_sample() -> tuple[dict[str, str], str]:
    live_path = RAW_DIR / "live_weather_observations.csv"
    if live_path.exists():
        return read_latest_esp32(live_path), "esp32_tcp_open_meteo"
    return read_latest_esp32(RAW_DIR / "esp32_usb_samples.csv"), "esp32_usb_open_meteo"


def main() -> int:
    current_path = RAW_DIR / "current_weather.json"
    out_json = RAW_DIR / "current_weather_combined.json"
    out_csv = RAW_DIR / "current_weather_combined.csv"

    current = json.loads(current_path.read_text(encoding="utf-8"))
    latest, tangshan_source = read_latest_tangshan_sample()

    combined = []
    for item in current:
        record = dict(item)
        if record["id"] == "tangshan":
            record["time"] = latest["collect_time"]
            record["temperature"] = float(latest["temperature"])
            record["humidity"] = float(latest["humidity"])
            record["source"] = tangshan_source
        else:
            record["source"] = "open_meteo"
        combined.append(record)

    out_json.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            lineterminator="\n",
            fieldnames=[
                "time",
                "id",
                "name",
                "latitude",
                "longitude",
                "temperature",
                "humidity",
                "pressure",
                "wind_speed",
                "wind_direction",
                "weather_code",
                "source",
            ],
        )
        writer.writeheader()
        for row in combined:
            writer.writerow(
                {
                    "time": row["time"],
                    "id": row["id"],
                    "name": row["name"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "temperature": row["temperature"],
                    "humidity": row["humidity"],
                    "pressure": row["pressure"],
                    "wind_speed": row["wind_speed"],
                    "wind_direction": row["wind_direction"],
                    "weather_code": row["weather_code"],
                    "source": row["source"],
                }
            )

    print(f"wrote {out_json}")
    print(f"wrote {out_csv}")
    print(f"merged_at={datetime.now().astimezone().isoformat(timespec='seconds')}")
    for row in combined:
        print(
            "{id},{name},{temperature},{humidity},{pressure},{wind_speed},{wind_direction},{weather_code},{source}".format(
                **row
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
