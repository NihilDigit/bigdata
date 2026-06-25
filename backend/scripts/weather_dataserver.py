#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
FIELDNAMES = [
    "collect_time",
    "station_id",
    "station_name",
    "temperature",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_direction",
    "weather_code",
    "sample_seq",
]
HDFS_FIELDNAMES = [
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
STATION_IDS = {
    "唐山": "tangshan",
    "北京": "beijing",
    "上海": "shanghai",
}
STATION_NAMES = {value: key for key, value in STATION_IDS.items()}
STATIONS = {
    "tangshan": {"name": "唐山", "latitude": 39.63, "longitude": 118.18},
    "beijing": {"name": "北京", "latitude": 39.90, "longitude": 116.40},
    "shanghai": {"name": "上海", "latitude": 31.23, "longitude": 121.47},
}
OPENMETEO_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "weather_code",
]


@dataclass
class WeatherRecord:
    collect_time: str
    station_id: str
    station_name: str
    temperature: float
    humidity: float
    pressure: float
    wind_speed: float
    wind_direction: float
    weather_code: int
    sample_seq: int | None = None

    def as_row(self) -> dict[str, Any]:
        return {
            "collect_time": self.collect_time,
            "station_id": self.station_id,
            "station_name": self.station_name,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "pressure": self.pressure,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "weather_code": self.weather_code,
            "sample_seq": self.sample_seq,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Receive weather station pushes over WebSocket and write HBase/HDFS inputs."
    )
    parser.add_argument("--ws-host", default="0.0.0.0")
    parser.add_argument("--ws-port", type=int, default=8080)
    parser.add_argument("--openmeteo-refresh-minutes", type=float, default=10.0)
    parser.add_argument("--local-out", default=str(RAW_DIR / "live_weather_observations.csv"))
    parser.add_argument("--hdfs-dir", default="/weathertextdb")
    parser.add_argument("--hbase-table", default="realtime_weather")
    parser.add_argument("--hbase-host", default="127.0.0.1")
    parser.add_argument("--hbase-port", type=int, default=9090)
    parser.add_argument("--hbase-ttl", type=int, default=150)
    parser.add_argument("--flush-size", type=int, default=10)
    parser.add_argument("--max-records", type=int, default=0, help="0 means run forever")
    parser.add_argument("--no-hdfs", action="store_true")
    parser.add_argument("--no-hbase", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def fetch_current_by_station() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for station_id, station in STATIONS.items():
        query = urlencode(
            {
                "latitude": station["latitude"],
                "longitude": station["longitude"],
                "current": ",".join(OPENMETEO_FIELDS),
                "wind_speed_unit": "ms",
                "timezone": "Asia/Shanghai",
            }
        )
        with urlopen(f"https://api.open-meteo.com/v1/forecast?{query}", timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
        current = payload["current"]
        records[station_id] = {
            "id": station_id,
            "name": station["name"],
            "temperature": current["temperature_2m"],
            "humidity": current["relative_humidity_2m"],
            "pressure": current["surface_pressure"],
            "wind_speed": current["wind_speed_10m"],
            "wind_direction": current["wind_direction_10m"],
            "weather_code": current["weather_code"],
        }
    return records


def normalize_station_id(value: str) -> str:
    return STATION_IDS.get(value, value)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def fallback_float(fallback: dict[str, Any], key: str) -> float:
    return float(fallback.get(key, 0) or 0)


def jitter_value(base: float, radius: float, floor: float | None = None, ceiling: float | None = None) -> float:
    value = base + random.uniform(-radius, radius)
    if floor is not None:
        value = max(floor, value)
    if ceiling is not None:
        value = min(ceiling, value)
    return round(value, 2)


def parse_station_payload(payload: dict[str, Any], current: dict[str, dict[str, Any]], received_at: str) -> WeatherRecord:
    station_id = normalize_station_id(str(payload.get("station_id") or payload.get("id") or ""))
    if not station_id:
        raise ValueError("missing station_id")
    fallback = current.get(station_id, {})
    station_name = str(payload.get("station_name") or payload.get("name") or fallback.get("name") or STATION_NAMES.get(station_id, station_id))
    return WeatherRecord(
        collect_time=received_at,
        station_id=station_id,
        station_name=station_name,
        temperature=float(payload.get("temperature")),
        humidity=float(payload.get("humidity")),
        pressure=float(payload["pressure"]) if payload.get("pressure") not in ("", None) else jitter_value(fallback_float(fallback, "pressure"), 0.5),
        wind_speed=float(payload["wind_speed"]) if payload.get("wind_speed") not in ("", None) else jitter_value(fallback_float(fallback, "wind_speed"), 0.5, floor=0.0),
        wind_direction=float(payload["wind_direction"]) if payload.get("wind_direction") not in ("", None) else round((fallback_float(fallback, "wind_direction") + random.uniform(-5, 5)) % 360, 2),
        weather_code=int(float(payload.get("weather_code", fallback.get("weather_code", 0) or 0))),
        sample_seq=int(payload["sample_seq"]) if payload.get("sample_seq") not in ("", None) else None,
    )


def parse_station_csv(line: str, current: dict[str, dict[str, Any]], received_at: str) -> WeatherRecord:
    parts = [part.strip() for part in line.strip().split(",")]
    if len(parts) in (4, 5):
        station_id, station_name, temperature, humidity = parts[:4]
        payload: dict[str, Any] = {
            "station_id": station_id,
            "station_name": station_name,
            "temperature": temperature,
            "humidity": humidity,
        }
        if len(parts) == 5:
            payload["sample_seq"] = parts[4]
        return parse_station_payload(payload, current, received_at)
    if len(parts) == 9:
        (
            collect_time,
            station_id,
            station_name,
            temperature,
            humidity,
            pressure,
            wind_speed,
            wind_direction,
            weather_code,
        ) = parts
        return parse_station_payload(
            {
                "collect_time": collect_time,
                "station_id": station_id,
                "station_name": station_name,
                "temperature": temperature,
                "humidity": humidity,
                "pressure": pressure,
                "wind_speed": wind_speed,
                "wind_direction": wind_direction,
                "weather_code": weather_code,
            },
            current,
            received_at,
        )
    raise ValueError(f"unsupported station CSV format with {len(parts)} columns: {line!r}")


def parse_station_message(message: str | bytes, current: dict[str, dict[str, Any]]) -> WeatherRecord:
    received_at = now_iso()
    text = message.decode("utf-8") if isinstance(message, bytes) else message
    text = text.strip()
    if not text:
        raise ValueError("empty station message")
    if text.startswith("{"):
        return parse_station_payload(json.loads(text), current, received_at)
    return parse_station_csv(text, current, received_at)


def ensure_local_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames == FIELDNAMES:
                return
            rows = [{field: row.get(field, "") for field in FIELDNAMES} for row in reader]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()


def append_local(path: Path, records: list[WeatherRecord]) -> None:
    ensure_local_csv(path)
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        for record in records:
            writer.writerow(record.as_row())


def run_distro(command: str, dry_run: bool) -> None:
    if dry_run:
        print(f"dry-run distro command: {command}")
        return
    subprocess.run([str(ROOT / "scripts" / "distro-bigdata.sh"), command], check=True)


def flush_hdfs(records: list[WeatherRecord], hdfs_dir: str, dry_run: bool) -> None:
    batch_dir = ROOT / ".runtime" / "hdfs-batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = batch_dir / f"live_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.csv"
    with tmp_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HDFS_FIELDNAMES)
        for record in records:
            row = record.as_row()
            writer.writerow({field: row[field] for field in HDFS_FIELDNAMES})
    batch_name = f"live_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.csv"
    try:
        run_distro(
            f"hdfs dfs -mkdir -p {hdfs_dir} && hdfs dfs -put -f {tmp_path} {hdfs_dir}/{batch_name}",
            dry_run=dry_run,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


def hbase_row_key(record: WeatherRecord) -> str:
    timestamp = (
        record.collect_time.replace("-", "")
        .replace(":", "")
        .replace("T", "")
        .replace("+08:00", "")
        .replace(".", "")
        .replace(" ", "")
    )
    return f"{record.station_id}_{timestamp[:17]}"


def ensure_hbase_table(args: argparse.Namespace) -> None:
    if args.no_hbase:
        return
    if args.dry_run:
        print(f"dry-run ensure hbase table: {args.hbase_table}")
        return
    import happybase  # type: ignore[import-not-found]

    connection = happybase.Connection(args.hbase_host, port=args.hbase_port, timeout=3000)
    try:
        table_name = args.hbase_table.encode("utf-8")
        if table_name not in connection.tables():
            connection.create_table(
                args.hbase_table,
                {"data": {"time_to_live": str(args.hbase_ttl)}},
            )
    finally:
        connection.close()


def flush_hbase(records: list[WeatherRecord], args: argparse.Namespace) -> None:
    if args.dry_run:
        print(f"dry-run hbase put: table={args.hbase_table} records={len(records)}")
        return
    import happybase  # type: ignore[import-not-found]

    connection = happybase.Connection(args.hbase_host, port=args.hbase_port, timeout=3000)
    try:
        table = connection.table(args.hbase_table)
        with table.batch(batch_size=max(1, len(records))) as batch:
            for record in records:
                row = {
                    f"data:{field}".encode("utf-8"): str(value).encode("utf-8")
                    for field, value in record.as_row().items()
                    if field != "station_id" and value is not None
                }
                batch.put(hbase_row_key(record), row)
    finally:
        connection.close()


def flush_records(args: argparse.Namespace, records: list[WeatherRecord]) -> None:
    if not records:
        return
    append_local(Path(args.local_out), records)
    if not args.no_hdfs:
        flush_hdfs(records, args.hdfs_dir, args.dry_run)
    if not args.no_hbase:
        flush_hbase(records, args)


def log_record(record: WeatherRecord) -> None:
    print(
        "record {collect_time} {station_name} temp={temperature} humidity={humidity}".format(
            **record.as_row()
        )
    )


class WsIngestState:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.current = fetch_current_by_station()
        self.refresh_at = datetime.now() + timedelta(minutes=args.openmeteo_refresh_minutes)
        self.batch: list[WeatherRecord] = []
        self.flush_queue: asyncio.Queue[list[WeatherRecord]] = asyncio.Queue()
        self.flush_worker_task = asyncio.create_task(self.flush_worker())
        self.total = 0
        self.lock = asyncio.Lock()
        self.stop = asyncio.Event()

    def schedule_flush(self, records: list[WeatherRecord]) -> None:
        self.flush_queue.put_nowait(records)

    async def flush_worker(self) -> None:
        while True:
            records = await self.flush_queue.get()
            try:
                await asyncio.to_thread(flush_records, self.args, records)
                print(f"flushed records={len(records)} total={self.total} queue={self.flush_queue.qsize()}")
            except Exception as exc:
                print(f"flush failed records={len(records)}: {exc}")
            finally:
                self.flush_queue.task_done()

    async def add_message(self, message: str | bytes) -> None:
        if datetime.now() >= self.refresh_at:
            self.current = fetch_current_by_station()
            self.refresh_at = datetime.now() + timedelta(minutes=self.args.openmeteo_refresh_minutes)
            print(f"refreshed open-meteo current next={self.refresh_at.isoformat(timespec='seconds')}")
        try:
            record = parse_station_message(message, self.current)
        except Exception as exc:
            print(f"skip malformed websocket message: {message!r}: {exc}")
            return
        async with self.lock:
            self.batch.append(record)
            self.total += 1
            log_record(record)
            if len(self.batch) >= self.args.flush_size:
                self.schedule_flush(list(self.batch))
                self.batch.clear()
            if self.args.max_records and self.total >= self.args.max_records:
                if self.batch:
                    self.schedule_flush(list(self.batch))
                    self.batch.clear()
                await self.flush_queue.join()
                self.stop.set()


async def receive_ws_records(args: argparse.Namespace) -> int:
    try:
        import websockets
    except ImportError as exc:
        raise SystemExit("Install websockets or run with `uvx --with websockets python backend/scripts/weather_dataserver.py`.") from exc

    ensure_hbase_table(args)
    state = WsIngestState(args)

    async def handler(websocket: Any, path: str | None = None) -> None:
        peer = getattr(websocket, "remote_address", "unknown")
        print(f"station websocket connected peer={peer} path={path or '/'}")
        async for message in websocket:
            await state.add_message(message)
            if state.stop.is_set():
                await websocket.close()
                break

    print(f"weather websocket server listening ws://{args.ws_host}:{args.ws_port}")
    async with websockets.serve(handler, args.ws_host, args.ws_port, ping_interval=None):
        await state.stop.wait()
    state.flush_worker_task.cancel()
    return 0


def main() -> int:
    return asyncio.run(receive_ws_records(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
