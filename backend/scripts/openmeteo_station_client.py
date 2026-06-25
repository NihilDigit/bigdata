#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


HOURLY_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "weather_code",
]


@dataclass(frozen=True)
class Station:
    station_id: str
    name: str
    latitude: float
    longitude: float


STATIONS = {
    "beijing": Station("beijing", "北京", 39.90, 116.40),
    "shanghai": Station("shanghai", "上海", 31.23, 121.47),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push simulated station readings to the Weather Lab WS server.")
    parser.add_argument("station_id", choices=sorted(STATIONS))
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8080")
    parser.add_argument("--push-seconds", type=float, default=1.0)
    parser.add_argument("--refresh-minutes", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def fetch_current(station: Station) -> dict[str, Any]:
    query = urlencode(
        {
            "latitude": station.latitude,
            "longitude": station.longitude,
            "current": ",".join(HOURLY_FIELDS),
            "wind_speed_unit": "ms",
            "timezone": "Asia/Shanghai",
        }
    )
    with urlopen(f"https://api.open-meteo.com/v1/forecast?{query}", timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    current = payload["current"]
    return {
        "station_id": station.station_id,
        "station_name": station.name,
        "temperature": float(current["temperature_2m"]),
        "humidity": float(current["relative_humidity_2m"]),
        "pressure": float(current["surface_pressure"]),
        "wind_speed": float(current["wind_speed_10m"]),
        "wind_direction": float(current["wind_direction_10m"]),
        "weather_code": int(current["weather_code"]),
    }


def jitter(base: dict[str, Any], sample_seq: int) -> dict[str, Any]:
    return {
        "collect_time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "station_id": base["station_id"],
        "station_name": base["station_name"],
        "temperature": round(float(base["temperature"]) + random.uniform(-0.3, 0.3), 2),
        "humidity": round(max(0.0, min(100.0, float(base["humidity"]) + random.uniform(-2, 2))), 2),
        "pressure": round(float(base["pressure"]) + random.uniform(-0.5, 0.5), 2),
        "wind_speed": round(max(0.0, float(base["wind_speed"]) + random.uniform(-0.5, 0.5)), 2),
        "wind_direction": round((float(base["wind_direction"]) + random.uniform(-5, 5)) % 360, 2),
        "weather_code": int(base["weather_code"]),
        "sample_seq": sample_seq,
    }


async def main_async(args: argparse.Namespace) -> int:
    try:
        import websockets
    except ImportError as exc:
        raise SystemExit("Install websockets or run with `uvx --with websockets python backend/scripts/openmeteo_station_client.py`.") from exc

    if args.seed is not None:
        random.seed(args.seed)
    station = STATIONS[args.station_id]
    base: dict[str, Any] | None = None
    refresh_at = datetime.min
    sample_seq = 0
    async for websocket in websockets.connect(args.ws_url):
        try:
            while True:
                now = datetime.now()
                if base is None or now >= refresh_at:
                    base = fetch_current(station)
                    refresh_at = now + timedelta(minutes=args.refresh_minutes)
                    print(f"refreshed station={station.name} next={refresh_at.isoformat(timespec='seconds')}")
                sample_seq += 1
                record = jitter(base, sample_seq)
                await websocket.send(json.dumps(record, ensure_ascii=False))
                print(f"sent {record['station_name']} temp={record['temperature']} humidity={record['humidity']}")
                await asyncio.sleep(args.push_seconds)
        except Exception as exc:
            print(f"websocket disconnected: {exc}; reconnecting")
            continue


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
