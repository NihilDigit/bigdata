#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPARK_SERVER_HOST="${SPARK_SERVER_HOST:-127.0.0.1}"
SPARK_SERVER_PORT="${SPARK_SERVER_PORT:-18081}"
HDFS_OUTPUT="${HDFS_OUTPUT:-/weather_analysis}"
COMPAT_OUTPUT="${COMPAT_OUTPUT:-/weather_10secmean}"
LOCAL_OUTPUT="${LOCAL_OUTPUT:-$PROJECT_ROOT/data/processed}"
WINDOW_SECONDS="${WINDOW_SECONDS:-10}"
SOURCE="${SOURCE:-csv}"
SOURCE_ARGS="--source csv"
if [[ "$SOURCE" == "hive" ]]; then
  SOURCE_ARGS="--source hive --hive-table weather_table"
fi

"$PROJECT_ROOT/scripts/distro-bigdata.sh" "
exec spark-submit --master yarn \
  '$PROJECT_ROOT/backend/scripts/spark_analysis_server.py' \
  --host '$SPARK_SERVER_HOST' \
  --port '$SPARK_SERVER_PORT' \
  --input-path /weathertextdb \
  --hdfs-output '$HDFS_OUTPUT' \
  --local-output '$LOCAL_OUTPUT' \
  $SOURCE_ARGS \
  --window-seconds '$WINDOW_SECONDS' \
  --compat-output '$COMPAT_OUTPUT'
"
