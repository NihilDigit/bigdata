#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


@dataclass(frozen=True)
class Station:
    station_id: str
    name: str
    latitude: float
    longitude: float


STATIONS = [
    Station("tangshan", "唐山", 39.63, 118.18),
    Station("beijing", "北京", 39.90, 116.40),
    Station("shanghai", "上海", 31.23, 121.47),
]

HOURLY_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "weather_code",
]


def fetch_json(url: str) -> dict:
    with urlopen(url, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def build_url(station: Station) -> str:
    query = urlencode(
        {
            "latitude": station.latitude,
            "longitude": station.longitude,
            "current": ",".join(HOURLY_FIELDS),
            "hourly": ",".join(HOURLY_FIELDS),
            "past_days": 7,
            "forecast_days": 1,
            "wind_speed_unit": "ms",
            "timezone": "Asia/Shanghai",
        }
    )
    return f"https://api.open-meteo.com/v1/forecast?{query}"


def build_historical_url(station: Station, start_date: date, end_date: date) -> str:
    query = urlencode(
        {
            "latitude": station.latitude,
            "longitude": station.longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": ",".join(HOURLY_FIELDS),
            "wind_speed_unit": "ms",
            "timezone": "Asia/Shanghai",
        }
    )
    return f"https://archive-api.open-meteo.com/v1/archive?{query}"


def normalize_number(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def write_outputs(out_dir: Path, days: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    records_path = out_dir / "weather_observations.csv"
    current_path = out_dir / "current_weather.json"
    meta_path = out_dir / "open_meteo_fetch_meta.json"

    rows: list[dict[str, str]] = []
    current_records: list[dict[str, object]] = []
    sources: dict[str, str] = {}
    historical_sources: dict[str, str] = {}
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)

    for station in STATIONS:
        url = build_url(station)
        payload = fetch_json(url)
        sources[station.station_id] = url

        current = payload["current"]
        current_records.append(
            {
                "id": station.station_id,
                "name": station.name,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "time": current["time"],
                "temperature": current["temperature_2m"],
                "humidity": current["relative_humidity_2m"],
                "pressure": current["surface_pressure"],
                "wind_speed": current["wind_speed_10m"],
                "wind_direction": current["wind_direction_10m"],
                "weather_code": current["weather_code"],
            }
        )

        historical_url = build_historical_url(station, start_date, end_date)
        historical_payload = fetch_json(historical_url)
        historical_sources[station.station_id] = historical_url
        hourly = historical_payload["hourly"]
        for idx, collect_time in enumerate(hourly["time"]):
            rows.append(
                {
                    "collect_time": collect_time,
                    "station_id": station.station_id,
                    "station_name": station.name,
                    "temperature": normalize_number(hourly["temperature_2m"][idx]),
                    "humidity": normalize_number(hourly["relative_humidity_2m"][idx]),
                    "pressure": normalize_number(hourly["surface_pressure"][idx]),
                    "wind_speed": normalize_number(hourly["wind_speed_10m"][idx]),
                    "wind_direction": normalize_number(hourly["wind_direction_10m"][idx]),
                    "weather_code": normalize_number(hourly["weather_code"][idx]),
                }
            )

    rows.sort(key=lambda row: (row["collect_time"], row["station_id"]))

    fieldnames = [
        "collect_time",
        "station_id",
        "station_name",
        "temperature",
        "humidity",
        "pressure",
        "wind_speed",
        "wind_direction",
        "weather_code",
    ]
    with records_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    current_path.write_text(
        json.dumps(current_records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    meta_path.write_text(
        json.dumps(
            {
                "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "record_count": len(rows),
                "station_count": len(STATIONS),
                "historical_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "current_sources": sources,
                "historical_sources": historical_sources,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"wrote {records_path}")
    print(f"wrote {current_path}")
    print(f"wrote {meta_path}")
    print(f"records={len(rows)} stations={len(STATIONS)}")
    if rows:
        print(f"time_range={rows[0]['collect_time']}..{rows[-1]['collect_time']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", nargs="?", default="data/raw")
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()
    if args.days < 1:
        raise SystemExit("--days must be >= 1")
    write_outputs(Path(args.out_dir), args.days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
