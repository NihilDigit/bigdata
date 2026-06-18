#!/usr/bin/env bash
set -euo pipefail

csv_path="${1:-$WEATHER_DATA_DIR/raw/weather_observations.csv}"
if [[ ! -f "$csv_path" ]]; then
  echo "CSV not found: $csv_path" >&2
  exit 1
fi

tmp_body="$(dirname "$csv_path")/weather_observations.body.csv"
mkdir -p "$(dirname "$tmp_body")"
tail -n +2 "$csv_path" > "$tmp_body"

abs_body="$(realpath "$tmp_body")"
"$(dirname "${BASH_SOURCE[0]}")/distro-bigdata.sh" "
hdfs dfs -mkdir -p /weather_lab/weathertextdb
hdfs dfs -put -f '$abs_body' /weather_lab/weathertextdb/weather_observations.csv
hdfs dfs -ls /weather_lab/weathertextdb
hdfs dfs -cat /weather_lab/weathertextdb/weather_observations.csv 2>/dev/null | sed -n '1,5p' || true
"
