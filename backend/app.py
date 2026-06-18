from __future__ import annotations

import csv
import json
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
    return read_json(RAW_DIR / "current_weather_combined.json")


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
