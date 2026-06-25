#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HDFS_OUTPUT="${HDFS_OUTPUT:-/weather_analysis}"
LOCAL_OUTPUT="${LOCAL_OUTPUT:-$PROJECT_ROOT/data/processed}"
WINDOW_SECONDS="${WINDOW_SECONDS:-10}"
SOURCE="${SOURCE:-csv}"
SOURCE_ARGS="--source csv"
if [[ "$SOURCE" == "hive" ]]; then
  SOURCE_ARGS="--source hive --hive-table weather_table"
fi

"$PROJECT_ROOT/scripts/distro-bigdata.sh" "
spark-submit --master yarn \
  '$PROJECT_ROOT/backend/scripts/spark_weather_analysis.py' \
  /weathertextdb \
  '$HDFS_OUTPUT' \
  '$LOCAL_OUTPUT' \
  $SOURCE_ARGS \
  --window-seconds '$WINDOW_SECONDS'
"
