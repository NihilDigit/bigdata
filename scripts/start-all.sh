#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${WEATHER_ALL_RUNTIME_DIR:-$PROJECT_ROOT/.runtime/all}"
LOG_DIR="$RUNTIME_DIR/logs"
PID_DIR="$RUNTIME_DIR/pids"

API_PORT="${API_PORT:-8008}"
WEB_PORT="${PORT:-3000}"
WS_PORT="${WS_PORT:-8080}"
SPARK_SERVER_PORT="${SPARK_SERVER_PORT:-18081}"
FLUSH_SIZE="${FLUSH_SIZE:-30}"
RUN_SPARK_ON_START="${RUN_SPARK_ON_START:-0}"

mkdir -p "$LOG_DIR" "$PID_DIR"

log() {
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

pid_file() {
  printf '%s/%s.pid' "$PID_DIR" "$1"
}

is_running_pid() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

service_pid() {
  local file
  file="$(pid_file "$1")"
  [[ -f "$file" ]] && cat "$file"
}

service_running() {
  local pid
  pid="$(service_pid "$1" 2>/dev/null || true)"
  is_running_pid "$pid"
}

port_listening() {
  local port="$1"
  ss -ltn "( sport = :$port )" 2>/dev/null | tail -n +2 | grep -q .
}

start_service() {
  local name="$1"
  local port="$2"
  shift 2
  local logfile="$LOG_DIR/$name.log"
  local pidfile
  pidfile="$(pid_file "$name")"

  if service_running "$name"; then
    log "$name already running pid=$(service_pid "$name")"
    return
  fi
  if [[ "$port" != "-" ]] && port_listening "$port"; then
    log "$name skipped: port $port is already listening"
    return
  fi

  log "starting $name -> $logfile"
  (
    cd "$PROJECT_ROOT"
    exec "$@"
  ) >>"$logfile" 2>&1 &
  echo "$!" >"$pidfile"
  log "$name pid=$(cat "$pidfile")"
}

stop_service() {
  local name="$1"
  local pid
  pid="$(service_pid "$name" 2>/dev/null || true)"
  if ! is_running_pid "$pid"; then
    rm -f "$(pid_file "$name")"
    log "$name not running"
    return
  fi

  log "stopping $name pid=$pid"
  pkill -TERM -P "$pid" >/dev/null 2>&1 || true
  kill "$pid" >/dev/null 2>&1 || true
  for _ in $(seq 1 10); do
    if ! is_running_pid "$pid"; then
      break
    fi
    sleep 0.5
  done
  if is_running_pid "$pid"; then
    log "force stopping $name pid=$pid"
    pkill -KILL -P "$pid" >/dev/null 2>&1 || true
    kill -KILL "$pid" >/dev/null 2>&1 || true
  fi
  rm -f "$(pid_file "$name")"
}

wait_http() {
  local name="$1"
  local url="$2"
  local seconds="${3:-60}"
  for _ in $(seq 1 "$seconds"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "$name ready: $url"
      return 0
    fi
    sleep 1
  done
  log "$name not ready after ${seconds}s: $url"
  return 1
}

start_bigdata() {
  log "starting Hadoop/YARN/HBase"
  "$PROJECT_ROOT/scripts/start-bigdata-services.sh" 2>&1 | tee "$LOG_DIR/bigdata.log"
}

start_all() {
  start_bigdata

  start_service weather-dataserver "$WS_PORT" \
    env UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
    uv run --with websockets --with happybase \
    python backend/scripts/weather_dataserver.py --flush-size "$FLUSH_SIZE"

  wait_http weather-ws "http://127.0.0.1:$WS_PORT" 2 || true

  start_service openmeteo-beijing "-" \
    env UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
    uv run --with websockets \
    python backend/scripts/openmeteo_station_client.py beijing --ws-url "ws://127.0.0.1:$WS_PORT"

  start_service openmeteo-shanghai "-" \
    env UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
    uv run --with websockets \
    python backend/scripts/openmeteo_station_client.py shanghai --ws-url "ws://127.0.0.1:$WS_PORT"

  start_service spark-analysis-server "$SPARK_SERVER_PORT" \
    env SPARK_SERVER_PORT="$SPARK_SERVER_PORT" \
    "$PROJECT_ROOT/scripts/run-spark-analysis-server.sh"

  wait_http spark-analysis-server "http://127.0.0.1:$SPARK_SERVER_PORT/health" 90 || true

  start_service web "$WEB_PORT" \
    env API_PORT="$API_PORT" PORT="$WEB_PORT" \
    "$PROJECT_ROOT/scripts/run-web.sh"

  wait_http api "http://127.0.0.1:$API_PORT/" 45 || true
  wait_http web "http://127.0.0.1:$WEB_PORT/" 45 || true

  if [[ "$RUN_SPARK_ON_START" == "1" ]]; then
    log "submitting initial Spark refresh"
    curl -fsS -X POST "http://127.0.0.1:$API_PORT/api/analysis/refresh" >/dev/null || true
  fi

  log "ready"
  log "frontend: http://127.0.0.1:$WEB_PORT"
  log "api:      http://127.0.0.1:$API_PORT"
  log "ws:       ws://127.0.0.1:$WS_PORT"
  log "logs:     $LOG_DIR"
}

stop_all() {
  stop_service web
  stop_service spark-analysis-server
  stop_service openmeteo-shanghai
  stop_service openmeteo-beijing
  stop_service weather-dataserver
}

status_all() {
  for name in weather-dataserver openmeteo-beijing openmeteo-shanghai spark-analysis-server web; do
    if service_running "$name"; then
      log "$name running pid=$(service_pid "$name")"
    else
      log "$name stopped"
    fi
  done
  for item in "$API_PORT:api" "$WEB_PORT:web" "$WS_PORT:ws" "$SPARK_SERVER_PORT:spark"; do
    port="${item%%:*}"
    label="${item#*:}"
    if port_listening "$port"; then
      log "port $port listening ($label)"
    else
      log "port $port closed ($label)"
    fi
  done
}

case "${1:-start}" in
  start)
    start_all
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  status)
    status_all
    ;;
  *)
    echo "usage: $0 [start|stop|restart|status]" >&2
    exit 2
    ;;
esac
