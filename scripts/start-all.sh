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

port_pids() {
  local port="$1"
  ss -ltnp "( sport = :$port )" 2>/dev/null | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | sort -u
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
  printf '\n==== %s starting %s ====\n' "$(date '+%F %T')" "$name" >>"$logfile"
  (
    cd "$PROJECT_ROOT"
    exec nohup setsid "$@" < /dev/null
  ) >>"$logfile" 2>&1 &
  echo "$!" >"$pidfile"
  log "$name pid=$(cat "$pidfile")"
}

stop_service() {
  local name="$1"
  local port="${2:-}"
  local pid
  pid="$(service_pid "$name" 2>/dev/null || true)"
  if ! is_running_pid "$pid"; then
    rm -f "$(pid_file "$name")"
    log "$name not running"
  else
    log "stopping $name pid=$pid"
    kill -TERM "-$pid" >/dev/null 2>&1 || true
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
      kill -KILL "-$pid" >/dev/null 2>&1 || true
      pkill -KILL -P "$pid" >/dev/null 2>&1 || true
      kill -KILL "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$(pid_file "$name")"
  fi

  if [[ -n "$port" && "$port" != "-" ]]; then
    while read -r port_pid; do
      [[ -z "$port_pid" ]] && continue
      local pgid
      pgid="$(ps -o pgid= -p "$port_pid" 2>/dev/null | tr -d ' ' || true)"
      [[ -z "$pgid" ]] && continue
      log "stopping $name leftover pid=$port_pid pgid=$pgid on port $port"
      kill -TERM "-$pgid" >/dev/null 2>&1 || true
      for _ in $(seq 1 10); do
        if ! is_running_pid "$port_pid"; then
          break
        fi
        sleep 0.5
      done
      if is_running_pid "$port_pid"; then
        log "force stopping $name leftover pid=$port_pid pgid=$pgid"
        kill -KILL "-$pgid" >/dev/null 2>&1 || true
      fi
    done < <(port_pids "$port")
  fi
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

wait_port() {
  local name="$1"
  local port="$2"
  local seconds="${3:-60}"
  for _ in $(seq 1 "$seconds"); do
    if port_listening "$port"; then
      log "$name ready: port $port"
      return 0
    fi
    sleep 1
  done
  log "$name not ready after ${seconds}s: port $port"
  return 1
}

wait_hdfs_ready() {
  local seconds="${1:-90}"
  log "waiting for HDFS safe mode to turn off"
  for _ in $(seq 1 "$seconds"); do
    if "$PROJECT_ROOT/scripts/distro-bigdata.sh" "hdfs dfsadmin -safemode get 2>/dev/null | grep -q OFF" >/dev/null 2>&1; then
      log "HDFS safe mode is OFF"
      return 0
    fi
    sleep 1
  done
  log "HDFS still not ready after ${seconds}s"
  return 1
}

wait_hbase_thrift() {
  local seconds="${1:-90}"
  log "waiting for HBase Thrift"
  for _ in $(seq 1 "$seconds"); do
    if (
      cd "$PROJECT_ROOT"
      UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run --with happybase python -c \
        'import happybase; c=happybase.Connection("127.0.0.1", port=9090, timeout=1500); c.tables(); c.close()'
    ) >/dev/null 2>&1; then
      log "HBase Thrift is ready"
      return 0
    fi
    sleep 1
  done
  log "HBase Thrift not ready after ${seconds}s"
  return 1
}

start_bigdata() {
  log "starting Hadoop/YARN/HBase"
  "$PROJECT_ROOT/scripts/start-bigdata-services.sh" 2>&1 | tee "$LOG_DIR/bigdata.log"
}

stop_bigdata() {
  log "stopping Hadoop/YARN/HBase"
  "$PROJECT_ROOT/scripts/prepare-runtime-conf.sh" >/dev/null
  "$PROJECT_ROOT/scripts/distro-bigdata.sh" '
stop_hbase_daemon() {
  local process="$1"
  local daemon="$2"
  shift 2
  if jps | awk "{print \$2}" | grep -qx "$process"; then
    hbase-daemon.sh stop "$daemon" "$@" || true
  else
    echo "$process not running"
  fi
}

stop_hdfs_daemon() {
  local process="$1"
  local daemon="$2"
  if jps | awk "{print \$2}" | grep -qx "$process"; then
    hdfs --daemon stop "$daemon" || true
  else
    echo "$process not running"
  fi
}

stop_hbase_daemon ThriftServer thrift -p 9090
stop_hbase_daemon HRegionServer regionserver
stop_hbase_daemon HMaster master
stop_hbase_daemon HQuorumPeer zookeeper

if jps | awk "{print \$2}" | grep -qx NodeManager; then
  yarn --daemon stop nodemanager || true
else
  echo "NodeManager not running"
fi
if jps | awk "{print \$2}" | grep -qx ResourceManager; then
  yarn --daemon stop resourcemanager || true
else
  echo "ResourceManager not running"
fi

stop_hdfs_daemon SecondaryNameNode secondarynamenode
stop_hdfs_daemon DataNode datanode
stop_hdfs_daemon NameNode namenode

echo "Current Java processes"
jps
'
}

start_all() {
  start_bigdata
  wait_hdfs_ready 90 || return 1
  wait_hbase_thrift 90 || return 1

  start_service weather-dataserver "$WS_PORT" \
    env PYTHONUNBUFFERED=1 UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
    uv run --with websockets --with happybase \
    python backend/scripts/weather_dataserver.py --flush-size "$FLUSH_SIZE"

  wait_port weather-ws "$WS_PORT" 30 || return 1

  start_service openmeteo-beijing "-" \
    env UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
    uv run --with websockets \
    python backend/scripts/openmeteo_station_client.py beijing --ws-url "ws://127.0.0.1:$WS_PORT"

  start_service openmeteo-shanghai "-" \
    env UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
    uv run --with websockets \
    python backend/scripts/openmeteo_station_client.py shanghai --ws-url "ws://127.0.0.1:$WS_PORT"

  start_service spark-analysis-server "$SPARK_SERVER_PORT" \
    env SPARK_SERVER_PORT="$SPARK_SERVER_PORT" SPARK_RAW_LOG_PATH="$LOG_DIR/spark-analysis-server.log" \
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
  stop_service web "$WEB_PORT"
  stop_service spark-analysis-server "$SPARK_SERVER_PORT"
  stop_service openmeteo-shanghai
  stop_service openmeteo-beijing
  stop_service weather-dataserver "$WS_PORT"
  stop_bigdata
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
