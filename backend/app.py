from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


app = FastAPI(title="Weather Lab API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8008",
        "http://localhost:8008",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)
STATIONS = [
    {"id": "tangshan", "name": "唐山", "latitude": 39.63, "longitude": 118.18},
    {"id": "beijing", "name": "北京", "latitude": 39.90, "longitude": 116.40},
    {"id": "shanghai", "name": "上海", "latitude": 31.23, "longitude": 121.47},
]

METRICS = [
    {"id": "temperature", "name": "温度", "unit": "°C"},
    {"id": "humidity", "name": "湿度", "unit": "%"},
    {"id": "pressure", "name": "气压", "unit": "hPa"},
    {"id": "wind_speed", "name": "风速", "unit": "m/s"},
    {"id": "wind_direction", "name": "风向", "unit": "°"},
]


def read_json(path: Path) -> Any:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"missing data file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"missing data file: {path.relative_to(ROOT)}")
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def coerce_weather_row(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    for key in ("temperature", "humidity", "pressure", "wind_speed", "wind_direction"):
        if key in result and result[key] not in ("", None):
            result[key] = float(result[key])
    if result.get("weather_code") not in ("", None):
        result["weather_code"] = int(float(result["weather_code"]))
    if result.get("sample_seq") not in ("", None):
        result["sample_seq"] = int(float(result["sample_seq"]))
    return result


def live_rows() -> list[dict[str, Any]]:
    path = RAW_DIR / "live_weather_observations.csv"
    if not path.exists():
        return []
    rows = []
    for row in read_csv(path):
        row.setdefault("source", "esp32_tcp_open_meteo")
        rows.append(coerce_weather_row(row))
    return rows


def latest_live_by_station() -> dict[str, dict[str, Any]]:
    latest: dict[str, tuple[datetime, dict[str, Any]]] = {}
    for row in live_rows():
        station_id = row.get("station_id")
        collect_ts = parse_time(str(row.get("collect_time", "")))
        if not station_id or not collect_ts:
            continue
        if station_id not in latest or collect_ts > latest[station_id][0]:
            latest[station_id] = (collect_ts, row)
    return {station_id: row for station_id, (_, row) in latest.items()}


def hbase_current_by_station() -> dict[str, dict[str, Any]]:
    try:
        import happybase  # type: ignore[import-not-found]
    except Exception:
        return {}
    try:
        connection = happybase.Connection(
            os.environ.get("HBASE_THRIFT_HOST", "127.0.0.1"),
            port=int(os.environ.get("HBASE_THRIFT_PORT", "9090")),
            timeout=1500,
        )
        table = connection.table(os.environ.get("HBASE_WEATHER_TABLE", "realtime_weather"))
        latest: dict[str, tuple[str, dict[str, Any]]] = {}
        station_meta = {station["id"]: station for station in STATIONS}
        for key, data in table.scan(columns=[b"data"]):
            row_key = key.decode("utf-8", errors="replace")
            station_id = row_key.split("_", 1)[0]
            values = {
                column.decode("utf-8", errors="replace").split(":", 1)[1]: value.decode(
                    "utf-8", errors="replace"
                )
                for column, value in data.items()
            }
            meta = station_meta.get(station_id, {})
            record = {
                "id": station_id,
                "name": values.get("station_name", meta.get("name", station_id)),
                "latitude": float(values.get("latitude", meta.get("latitude", 0))),
                "longitude": float(values.get("longitude", meta.get("longitude", 0))),
                "time": values.get("collect_time", ""),
                "temperature": values.get("temperature", 0),
                "humidity": values.get("humidity", 0),
                "pressure": values.get("pressure", 0),
                "wind_speed": values.get("wind_speed", 0),
                "wind_direction": values.get("wind_direction", 0),
                "weather_code": values.get("weather_code", 0),
                "source": values.get("source", "hbase"),
            }
            record = coerce_weather_row(record)
            collect_time = str(record.get("time", ""))
            if station_id not in latest or collect_time > latest[station_id][0]:
                latest[station_id] = (collect_time, record)
        connection.close()
        return {station_id: record for station_id, (_, record) in latest.items()}
    except Exception:
        return {}


def station_ids() -> set[str]:
    return {station["id"] for station in STATIONS}


def ensure_station(station_id: str) -> None:
    if station_id not in station_ids():
        raise HTTPException(status_code=404, detail=f"unknown station_id: {station_id}")


def ensure_metric(metric: str) -> None:
    if metric not in {item["id"] for item in METRICS}:
        raise HTTPException(status_code=404, detail=f"unknown metric: {metric}")


def filter_station(rows: list[dict[str, Any]], station_id: str | None) -> list[dict[str, Any]]:
    if not station_id:
        return rows
    ensure_station(station_id)
    return [row for row in rows if row.get("station_id") == station_id or row.get("id") == station_id]


@app.get("/")
def index() -> dict[str, str]:
    return {
        "name": "Weather Lab API",
        "frontend": "Run Next.js from frontend/ on http://127.0.0.1:3000",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


def current_weather() -> list[dict[str, Any]]:
    current = read_json(RAW_DIR / "current_weather_combined.json")
    overlays = [hbase_current_by_station(), latest_live_by_station()]
    if not any(overlays):
        return current
    merged = []
    for item in current:
        record = dict(item)
        for overlay in overlays:
            live = overlay.get(record["id"])
            if live:
                record.update(
                    {
                        "time": live.get("time", live.get("collect_time")),
                        "temperature": live["temperature"],
                        "humidity": live["humidity"],
                        "pressure": live["pressure"],
                        "wind_speed": live["wind_speed"],
                        "wind_direction": live["wind_direction"],
                        "weather_code": live["weather_code"],
                        "source": live.get("source", "hbase"),
                    }
                )
        merged.append(record)
    return merged


@app.get("/api/stations/current")
def stations_current() -> list[dict[str, Any]]:
    return current_weather()


@app.get("/api/stations")
def stations() -> list[dict[str, Any]]:
    current = {row["id"]: row for row in current_weather()}
    return [{**station, "current": current.get(station["id"])} for station in STATIONS]


@app.get("/api/metrics")
def metrics() -> list[dict[str, str]]:
    return METRICS


@app.get("/api/summary")
def station_summary() -> list[dict[str, Any]]:
    return read_json(PROCESSED_DIR / "station_summary.json")


@app.get("/api/analysis/summary")
def analysis_summary() -> list[dict[str, Any]]:
    return station_summary()


@app.get("/api/daily")
def daily_summary(station_id: str | None = None) -> list[dict[str, Any]]:
    rows = read_json(PROCESSED_DIR / "daily_summary.json")
    if station_id:
        rows = [row for row in rows if row["station_id"] == station_id]
    return rows


@app.get("/api/hourly")
def hourly_series(station_id: str | None = None) -> list[dict[str, Any]]:
    rows = read_json(PROCESSED_DIR / "hourly_series.json")
    return filter_station(rows, station_id)


@app.get("/api/analysis/trends")
def analysis_trends(
    station_id: str = Query(default="all"),
    metric: str = Query(default="temperature"),
    range: str = Query(default="7d"),
    granularity: str = Query(default="1h"),
) -> dict[str, Any]:
    ensure_metric(metric)
    effective_station = None if station_id == "all" else station_id
    rows = filter_station(read_json(PROCESSED_DIR / "hourly_series.json"), effective_station)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["station_id"], []).append(
            {
                "collect_time": row["collect_time"],
                "station_id": row["station_id"],
                "station_name": row["station_name"],
                metric: row[metric],
            }
        )
    return {
        "metric": next(item for item in METRICS if item["id"] == metric),
        "station_id": station_id,
        "range": range,
        "granularity": granularity,
        "series": grouped,
    }


@app.get("/api/stations/{station_id}/live")
def station_live(station_id: str, seconds: int = Query(default=150, ge=10, le=3600)) -> list[dict[str, Any]]:
    ensure_station(station_id)
    live = [row for row in live_rows() if row.get("station_id") == station_id]
    timed_live = [(parse_time(str(row.get("collect_time", ""))), row) for row in live]
    timed_live = [(ts, row) for ts, row in timed_live if ts is not None]
    if timed_live:
        timed_live.sort(key=lambda item: item[0])
        newest = max(ts for ts, _ in timed_live)
        cutoff = newest - timedelta(seconds=seconds)
        return [row for ts, row in timed_live if ts >= cutoff]
    rows = filter_station(read_json(PROCESSED_DIR / "hourly_series.json"), station_id)
    return rows[-min(len(rows), max(1, seconds // 10)) :]


@app.get("/api/records")
def records(
    station_id: str | None = None,
    limit: int = Query(default=120, ge=1, le=504),
) -> list[dict[str, Any]]:
    rows = read_csv(RAW_DIR / "weather_observations.csv")
    rows = filter_station(rows, station_id)
    return rows[-limit:]


@app.get("/api/export/weather_observations.csv")
def export_weather_observations(station_id: str | None = None) -> StreamingResponse:
    rows = filter_station(read_csv(RAW_DIR / "weather_observations.csv"), station_id)
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
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    suffix = f"_{station_id}" if station_id else ""
    headers = {
        "Content-Disposition": f'attachment; filename="weather_observations{suffix}.csv"'
    }
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers=headers)
