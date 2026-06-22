#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HDFS_OUTPUT="${HDFS_OUTPUT:-/weather_analysis}"
COMPAT_OUTPUT="${COMPAT_OUTPUT:-/weather_10secmean}"
LOCAL_OUTPUT="${LOCAL_OUTPUT:-$PROJECT_ROOT/data/processed}"
WINDOW_SECONDS="${WINDOW_SECONDS:-10}"

"$PROJECT_ROOT/scripts/distro-bigdata.sh" "
spark-submit --master yarn \
  '$PROJECT_ROOT/backend/scripts/spark_weather_analysis.py' \
  /weathertextdb \
  '$HDFS_OUTPUT' \
  '$LOCAL_OUTPUT' \
  --source hive \
  --hive-table weather_table \
  --window-seconds '$WINDOW_SECONDS' \
  --compat-output '$COMPAT_OUTPUT'
"
