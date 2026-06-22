#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


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
    "station_name",
    "temperature",
    "humidity",
    "pressure",
    "wind_speed",
    "wind_direction",
]
STATION_IDS = {
    "唐山": "tangshan",
    "北京": "beijing",
    "上海": "shanghai",
}


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
        description="Receive ESP32 weather data over TCP and write HBase/HDFS pipeline inputs."
    )
    parser.add_argument("--station-host", required=True, help="ESP32 TCP server IP address")
    parser.add_argument("--station-port", type=int, default=8080)
    parser.add_argument("--current-json", default=str(RAW_DIR / "current_weather.json"))
    parser.add_argument("--local-out", default=str(RAW_DIR / "live_weather_observations.csv"))
    parser.add_argument("--hdfs-dir", default="/weathertextdb")
    parser.add_argument("--hbase-table", default="realtime_weather")
    parser.add_argument("--hbase-ttl", type=int, default=150)
    parser.add_argument("--flush-size", type=int, default=10)
    parser.add_argument("--max-records", type=int, default=0, help="0 means run forever")
    parser.add_argument("--connect-timeout", type=float, default=10)
    parser.add_argument("--retry-seconds", type=float, default=5)
    parser.add_argument("--no-hdfs", action="store_true")
    parser.add_argument("--no-hbase", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_current_by_station(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records = json.loads(path.read_text(encoding="utf-8"))
    return {row["id"]: row for row in records}


def normalize_station_id(value: str) -> str:
    return STATION_IDS.get(value, value)


def parse_station_line(line: str, current: dict[str, dict[str, Any]]) -> WeatherRecord:
    parts = [part.strip() for part in line.strip().split(",")]
    now = datetime.now().astimezone().isoformat(timespec="milliseconds")
    if len(parts) in (4, 5):
        station_id, station_name, temperature, humidity = parts[:4]
        sample_seq = int(parts[4]) if len(parts) == 5 and parts[4] else None
        station_id = normalize_station_id(station_id)
        fallback = current.get(station_id, {})
        return WeatherRecord(
            collect_time=now,
            station_id=station_id,
            station_name=station_name,
            temperature=float(temperature),
            humidity=float(humidity),
            pressure=float(fallback.get("pressure", 0)),
            wind_speed=float(fallback.get("wind_speed", 0)),
            wind_direction=float(fallback.get("wind_direction", 0)),
            weather_code=int(fallback.get("weather_code", 0)),
            sample_seq=sample_seq,
        )
    if len(parts) == 6:
        station_name, temperature, humidity, pressure, wind_speed, wind_direction = parts
        station_id = normalize_station_id(station_name)
        fallback = current.get(station_id, {})
        return WeatherRecord(
            collect_time=now,
            station_id=station_id,
            station_name=station_name,
            temperature=float(temperature),
            humidity=float(humidity),
            pressure=float(pressure),
            wind_speed=float(wind_speed),
            wind_direction=float(wind_direction),
            weather_code=int(fallback.get("weather_code", 0)),
        )
    if len(parts) == 7:
        collect_time, station_name, temperature, humidity, pressure, wind_speed, wind_direction = parts
        station_id = normalize_station_id(station_name)
        fallback = current.get(station_id, {})
        return WeatherRecord(
            collect_time=collect_time,
            station_id=station_id,
            station_name=station_name,
            temperature=float(temperature),
            humidity=float(humidity),
            pressure=float(pressure),
            wind_speed=float(wind_speed),
            wind_direction=float(wind_direction),
            weather_code=int(fallback.get("weather_code", 0)),
        )
    raise ValueError(f"unsupported ESP32 CSV format with {len(parts)} columns: {line!r}")


def ensure_local_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames == FIELDNAMES:
                return
            rows = [
                {field: row.get(field, "") for field in FIELDNAMES}
                for row in reader
            ]
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


def quote_hbase(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def write_hbase_script(path: Path, table: str, ttl: int, records: list[WeatherRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"table_name = {quote_hbase(table)}",
        f"create table_name, {{NAME => 'data', TTL => {ttl}}} unless exists(table_name)",
        f"alter table_name, {{NAME => 'data', TTL => {ttl}}}",
    ]
    for record in records:
        timestamp = (
            record.collect_time.replace("-", "")
            .replace(":", "")
            .replace("T", "")
            .replace("+08:00", "")
            .replace(".", "")
            .replace(" ", "")
        )
        row_key = f"{record.station_id}_{timestamp[:17]}"
        row = record.as_row()
        for field, value in row.items():
            if field == "station_id":
                continue
            lines.append(f"put table_name, {quote_hbase(row_key)}, {quote_hbase('data:' + field)}, {quote_hbase(value)}")
    lines.extend(["scan table_name, {LIMIT => 10}", "exit"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    run_distro(
        f"hdfs dfs -mkdir -p {hdfs_dir} && hdfs dfs -put -f {tmp_path} {hdfs_dir}/{batch_name}",
        dry_run=dry_run,
    )
    tmp_path.unlink(missing_ok=True)


def flush_hbase(records: list[WeatherRecord], table: str, ttl: int, dry_run: bool) -> None:
    script_path = PROCESSED_DIR / "hbase_live_weather_puts.hbase"
    write_hbase_script(script_path, table, ttl, records)
    run_distro(f"hbase shell -n {script_path}", dry_run=dry_run)


def flush_records(args: argparse.Namespace, records: list[WeatherRecord]) -> None:
    if not records:
        return
    append_local(Path(args.local_out), records)
    if not args.no_hdfs:
        flush_hdfs(records, args.hdfs_dir, args.dry_run)
    if not args.no_hbase:
        flush_hbase(records, args.hbase_table, args.hbase_ttl, args.dry_run)


def receive_records(args: argparse.Namespace) -> int:
    current = load_current_by_station(Path(args.current_json))
    total = 0
    batch: list[WeatherRecord] = []
    while args.max_records == 0 or total < args.max_records:
        try:
            with socket.create_connection(
                (args.station_host, args.station_port), timeout=args.connect_timeout
            ) as sock:
                print(f"connected station={args.station_host}:{args.station_port}")
                with sock.makefile("r", encoding="utf-8", newline="\n") as reader:
                    for raw_line in reader:
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            record = parse_station_line(line, current)
                        except Exception as exc:
                            print(f"skip malformed line: {line!r}: {exc}")
                            continue
                        batch.append(record)
                        total += 1
                        print(
                            "record {collect_time} {station_name} temp={temperature} humidity={humidity}".format(
                                **record.as_row()
                            )
                        )
                        if len(batch) >= args.flush_size:
                            flush_records(args, batch)
                            batch.clear()
                        if args.max_records and total >= args.max_records:
                            break
        except OSError as exc:
            print(f"station connection failed: {exc}; retry in {args.retry_seconds}s")
            time.sleep(args.retry_seconds)
        finally:
            if batch and (args.max_records and total >= args.max_records):
                flush_records(args, batch)
                batch.clear()
    if batch:
        flush_records(args, batch)
    return 0


def main() -> int:
    return receive_records(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
