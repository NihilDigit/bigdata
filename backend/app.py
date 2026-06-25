from __future__ import annotations

import csv
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
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
RUNTIME_DIR = ROOT / ".runtime"
SPARK_STATUS_PATH = RUNTIME_DIR / "spark-analysis-status.json"
SPARK_LOG_PATH = RUNTIME_DIR / "spark-analysis.log"
SPARK_SERVER_URL = os.environ.get("SPARK_ANALYSIS_SERVER_URL", "http://127.0.0.1:18081")
SPARK_SERVER_START_TIMEOUT = float(os.environ.get("SPARK_ANALYSIS_SERVER_START_TIMEOUT", "90"))
spark_server_process: subprocess.Popen[str] | None = None


app = FastAPI(title="Weather Lab API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8008",
        "http://localhost:8008",
    ],
    allow_methods=["GET", "POST"],
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


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def tail_lines(path: Path, limit: int = 80) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]


def tail_lines_from(path: Path, start_line: int | None, limit: int = 80) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if start_line is not None and start_line >= 0:
        lines = lines[start_line:]
    return lines[-limit:]


def read_spark_status() -> dict[str, Any]:
    if not SPARK_STATUS_PATH.exists():
        return {
            "job_id": None,
            "status": "idle",
            "message": "常驻 Spark driver 未启动",
            "log_tail": [],
        }
    status = json.loads(SPARK_STATUS_PATH.read_text(encoding="utf-8"))
    log_path = Path(status.get("log_path", SPARK_LOG_PATH))
    start_line = status.get("log_start_line")
    status["log_tail"] = tail_lines_from(log_path, start_line if isinstance(start_line, int) else None, 240)
    return status


def spark_server_json(path: str, method: str = "GET", timeout: float = 3) -> dict[str, Any]:
    request = urllib.request.Request(f"{SPARK_SERVER_URL}{path}", method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def spark_server_alive() -> bool:
    try:
        spark_server_json("/health", timeout=1)
        return True
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False


def spark_server_process_alive() -> bool:
    return spark_server_process is not None and spark_server_process.poll() is None


def start_spark_server() -> None:
    global spark_server_process
    if spark_server_alive():
        return
    if not spark_server_process_alive():
        command = [str(ROOT / "scripts" / "run-spark-analysis-server.sh")]
        status = {
            "job_id": None,
            "status": "running",
            "message": "常驻 Spark driver 启动中",
            "started_at": now_iso(),
            "completed_at": None,
            "exit_code": None,
            "pid": None,
            "command": " ".join(command),
            "log_path": str(SPARK_LOG_PATH),
            "progress_percent": 0,
            "progress_label": "启动 spark-submit 常驻服务",
        }
        write_json_atomic(SPARK_STATUS_PATH, status)
        SPARK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        boot_log = SPARK_LOG_PATH.open("a", encoding="utf-8")
        boot_log.write(f"[{now_iso()}] start {' '.join(command)}\n")
        boot_log.flush()
        spark_server_process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=boot_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    deadline = time.monotonic() + SPARK_SERVER_START_TIMEOUT
    while time.monotonic() < deadline:
        if spark_server_alive():
            return
        if spark_server_process and spark_server_process.poll() is not None:
            break
        time.sleep(1)
    current = read_spark_status()
    current.update(
        {
            "status": "failed" if spark_server_process and spark_server_process.poll() is not None else "running",
            "message": "常驻 Spark driver 仍在启动，请稍后查看状态",
            "progress_percent": current.get("progress_percent", 0),
            "progress_label": current.get("progress_label", "等待 Spark driver 就绪"),
        }
    )
    write_json_atomic(SPARK_STATUS_PATH, current)


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


def row_time_key(row: dict[str, Any]) -> str:
    return str(row.get("time") or row.get("collect_time") or "")


def hbase_current_by_station() -> dict[str, dict[str, Any]]:
    import happybase  # type: ignore[import-not-found]

    connection = happybase.Connection(
        os.environ.get("HBASE_THRIFT_HOST", "127.0.0.1"),
        port=int(os.environ.get("HBASE_THRIFT_PORT", "9090")),
        timeout=1500,
    )
    try:
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
            }
            record = coerce_weather_row(record)
            collect_time = str(record.get("time", ""))
            if station_id not in latest or collect_time > latest[station_id][0]:
                latest[station_id] = (collect_time, record)
        return {station_id: record for station_id, (_, record) in latest.items()}
    finally:
        connection.close()


def hbase_live_rows(station_id: str, seconds: int) -> list[dict[str, Any]]:
    import happybase  # type: ignore[import-not-found]

    connection = happybase.Connection(
        os.environ.get("HBASE_THRIFT_HOST", "127.0.0.1"),
        port=int(os.environ.get("HBASE_THRIFT_PORT", "9090")),
        timeout=1500,
    )
    try:
        table = connection.table(os.environ.get("HBASE_WEATHER_TABLE", "realtime_weather"))
        rows: list[dict[str, Any]] = []
        for key, data in table.scan(row_prefix=f"{station_id}_".encode(), columns=[b"data"]):
            values = {
                column.decode("utf-8", errors="replace").split(":", 1)[1]: value.decode(
                    "utf-8", errors="replace"
                )
                for column, value in data.items()
            }
            record = coerce_weather_row(
                {
                    "collect_time": values.get("collect_time", ""),
                    "station_id": station_id,
                    "station_name": values.get("station_name", station_id),
                    "temperature": values.get("temperature", 0),
                    "humidity": values.get("humidity", 0),
                    "pressure": values.get("pressure", 0),
                    "wind_speed": values.get("wind_speed", 0),
                    "wind_direction": values.get("wind_direction", 0),
                    "weather_code": values.get("weather_code", 0),
                    "sample_seq": values.get("sample_seq"),
                }
            )
            rows.append(record)
        timed_rows = [(parse_time(str(row.get("collect_time", ""))), row) for row in rows]
        timed_rows = [(ts, row) for ts, row in timed_rows if ts is not None]
        if not timed_rows:
            return []
        timed_rows.sort(key=lambda item: item[0])
        newest = max(ts for ts, _ in timed_rows)
        cutoff = newest - timedelta(seconds=seconds)
        return [row for ts, row in timed_rows if ts >= cutoff]
    finally:
        connection.close()


def hdfs_live_records(station_id: str | None, limit: int) -> list[dict[str, Any]]:
    raw_limit = max(limit * 8, 240)
    command = (
        "hdfs dfs -ls /weathertextdb/live_*.csv 2>/dev/null "
        "| awk '$8 !~ /_COPYING_$/ {print $8}' "
        "| tail -n 80 "
        "| xargs -r hdfs dfs -cat 2>/dev/null "
        f"| tail -n {raw_limit}"
    )
    result = subprocess.run(
        [str(ROOT / "scripts" / "distro-bigdata.sh"), command],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    rows: list[dict[str, Any]] = []
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
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("WARNING:"):
            continue
        try:
            row = next(csv.DictReader([line], fieldnames=fieldnames))
        except csv.Error:
            continue
        rows.append(coerce_weather_row(row))
    rows = filter_station(rows, station_id)
    return rows[-limit:]


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
    current = hbase_current_by_station()
    missing = station_ids() - set(current)
    if missing:
        raise HTTPException(status_code=503, detail=f"HBase current data missing stations: {sorted(missing)}")
    return [current[station["id"]] for station in STATIONS]


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


@app.post("/api/analysis/refresh")
def refresh_analysis() -> dict[str, Any]:
    start_spark_server()
    if not spark_server_alive():
        return read_spark_status()
    try:
        spark_server_json("/refresh", method="POST", timeout=5)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return read_spark_status()
    time.sleep(0.1)
    return read_spark_status()


@app.get("/api/analysis/refresh/status")
def refresh_analysis_status() -> dict[str, Any]:
    return read_spark_status()


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
    return hbase_live_rows(station_id, seconds)


@app.get("/api/records")
def records(
    station_id: str | None = None,
    limit: int = Query(default=120, ge=1, le=504),
) -> list[dict[str, Any]]:
    rows = read_csv(RAW_DIR / "weather_observations.csv")
    rows = filter_station(rows, station_id)
    return rows[-limit:]


@app.get("/api/hdfs/records")
def hdfs_records(
    station_id: str | None = None,
    limit: int = Query(default=120, ge=1, le=500),
) -> list[dict[str, Any]]:
    return hdfs_live_records(station_id, limit)


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
