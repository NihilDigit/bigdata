#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import threading
import time
import traceback
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from spark_weather_analysis import build_spark_session, run_analysis


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT / ".runtime"
STATUS_PATH = RUNTIME_DIR / "spark-analysis-status.json"
LOG_PATH = RUNTIME_DIR / "spark-analysis.log"
EVENT_LOG_PATH = RUNTIME_DIR / "spark-analysis-events.log"
RAW_LOG_PATH = Path(os.environ.get("SPARK_RAW_LOG_PATH", str(LOG_PATH)))


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


class Tee(io.TextIOBase):
    def __init__(self, *streams: io.TextIOBase) -> None:
        self.streams = streams

    def write(self, value: str) -> int:
        for stream in self.streams:
            if stream.closed:
                continue
            stream.write(value)
            stream.flush()
        return len(value)

    def flush(self) -> None:
        for stream in self.streams:
            if stream.closed:
                continue
            stream.flush()


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


class SparkAnalysisRuntime:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.lock = threading.Lock()
        self.job_thread: threading.Thread | None = None
        self.status: dict[str, Any] = {
            "job_id": None,
            "status": "idle",
            "message": "常驻 Spark driver 启动中",
            "started_at": None,
            "completed_at": None,
            "exit_code": None,
            "pid": os.getpid(),
            "command": "spark-analysis-server",
            "log_path": str(RAW_LOG_PATH),
            "event_log_path": str(EVENT_LOG_PATH),
            "log_start_line": None,
            "progress_percent": 0,
            "progress_label": "初始化 SparkSession",
        }
        write_json_atomic(STATUS_PATH, self.status)
        RAW_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.append_event(f"[{now_iso()}] starting persistent Spark driver pid={os.getpid()}")
        self.spark = build_spark_session(args)
        application_id = self.spark.sparkContext.applicationId
        self.set_status(
            status="idle",
            message="常驻 Spark driver 已就绪",
            application_id=application_id,
            progress_percent=0,
            progress_label="等待刷新请求",
        )
        self.append_event(f"[{now_iso()}] persistent Spark driver ready application_id={application_id}")

    def append_event(self, line: str) -> None:
        with EVENT_LOG_PATH.open("a", encoding="utf-8") as log:
            log.write(line.rstrip() + "\n")

    def set_status(self, **updates: Any) -> dict[str, Any]:
        with self.lock:
            self.status.update(updates)
            self.status["pid"] = os.getpid()
            self.status["log_path"] = str(RAW_LOG_PATH)
            self.status["event_log_path"] = str(EVENT_LOG_PATH)
            write_json_atomic(STATUS_PATH, self.status)
            return dict(self.status)

    def get_status(self) -> dict[str, Any]:
        with self.lock:
            return dict(self.status)

    def progress(self, label: str, percent: int) -> None:
        self.set_status(
            status="running",
            message=label,
            progress_percent=percent,
            progress_label=label,
        )

    def submit(self) -> dict[str, Any]:
        with self.lock:
            if self.job_thread and self.job_thread.is_alive():
                return dict(self.status)
            job_id = uuid.uuid4().hex[:12]
            self.status.update(
                {
                    "job_id": job_id,
                    "status": "running",
                    "message": "常驻 Spark driver 已接收刷新请求",
                    "started_at": now_iso(),
                    "completed_at": None,
                    "exit_code": None,
                    "progress_percent": 1,
                    "progress_label": "刷新请求入队",
                    "log_path": str(RAW_LOG_PATH),
                    "event_log_path": str(EVENT_LOG_PATH),
                    "log_start_line": count_lines(RAW_LOG_PATH),
                    "application_id": self.spark.sparkContext.applicationId,
                    "result": None,
                    "elapsed_seconds": None,
                }
            )
            write_json_atomic(STATUS_PATH, self.status)
            self.job_thread = threading.Thread(target=self.run_job, args=(job_id,), daemon=True)
            self.job_thread.start()
            return dict(self.status)

    def run_job(self, job_id: str) -> None:
        started = time.monotonic()
        self.append_event(f"[{now_iso()}] job_id={job_id} start persistent Spark refresh")
        try:
            with RAW_LOG_PATH.open("a", encoding="utf-8") as log:
                tee = Tee(log)
                with contextlib.redirect_stdout(tee), contextlib.redirect_stderr(tee):
                    result = run_analysis(self.spark, self.args, self.progress)
            elapsed = round(time.monotonic() - started, 2)
            self.append_event(f"[{now_iso()}] job_id={job_id} succeeded elapsed={elapsed}s")
            self.set_status(
                status="succeeded",
                message=f"Spark 重算完成，耗时 {elapsed}s",
                completed_at=now_iso(),
                exit_code=0,
                progress_percent=100,
                progress_label="Spark 重算完成",
                result=result,
                elapsed_seconds=elapsed,
            )
        except Exception as exc:
            elapsed = round(time.monotonic() - started, 2)
            self.append_event(f"[{now_iso()}] job_id={job_id} failed elapsed={elapsed}s error={exc}")
            self.append_event(traceback.format_exc())
            self.set_status(
                status="failed",
                message=f"Spark 重算失败：{exc}",
                completed_at=now_iso(),
                exit_code=1,
                progress_percent=100,
                progress_label="Spark 重算失败",
                elapsed_seconds=elapsed,
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--input-path", default="/weathertextdb")
    parser.add_argument("--hdfs-output", default="/weather_analysis")
    parser.add_argument("--local-output", default=str(ROOT / "data" / "processed"))
    parser.add_argument("--source", choices=["csv", "hive"], default="csv")
    parser.add_argument("--hive-table", default="weather_table")
    parser.add_argument("--window-seconds", type=int, default=10)
    parser.add_argument("--compat-output", default="/weather_10secmean")
    parser.add_argument("--no-compat-output", action="store_true")
    args = parser.parse_args()
    args.input_path = args.input_path
    args.hdfs_output = args.hdfs_output
    args.local_output = args.local_output
    return args


def make_analysis_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        input_path=args.input_path,
        hdfs_output=args.hdfs_output,
        local_output=args.local_output,
        source=args.source,
        hive_table=args.hive_table,
        window_seconds=args.window_seconds,
        compat_output=args.compat_output,
        no_compat_output=args.no_compat_output,
    )


class Handler(BaseHTTPRequestHandler):
    runtime: SparkAnalysisRuntime

    def log_message(self, fmt: str, *args: Any) -> None:
        self.runtime.append_event(f"[{now_iso()}] http {self.address_string()} {fmt % args}")

    def send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json({"ok": True, "pid": os.getpid()})
            return
        if self.path == "/status":
            self.send_json(self.runtime.get_status())
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path == "/refresh":
            self.send_json(self.runtime.submit())
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def main() -> int:
    args = parse_args()
    runtime = SparkAnalysisRuntime(make_analysis_args(args))
    Handler.runtime = runtime
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    runtime.append_event(f"[{now_iso()}] listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    finally:
        runtime.spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
