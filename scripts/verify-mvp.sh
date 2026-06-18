#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "== Local data files =="
python - <<'PY'
import csv
import json
from pathlib import Path

raw = Path("data/raw")
processed = Path("data/processed")
weather = list(csv.DictReader((raw / "weather_observations.csv").open(encoding="utf-8")))
current = json.loads((raw / "current_weather_combined.json").read_text(encoding="utf-8"))
summary = json.loads((processed / "station_summary.json").read_text(encoding="utf-8"))
hourly = json.loads((processed / "hourly_series.json").read_text(encoding="utf-8"))
meta = json.loads((raw / "open_meteo_fetch_meta.json").read_text(encoding="utf-8"))

print(f"weather_observations={len(weather)}")
print(f"current_stations={','.join(item['id'] for item in current)}")
print(f"summary={[(item['station_id'], item['records']) for item in summary]}")
print(f"hourly_series={len(hourly)}")
print(f"historical_range={meta['historical_range']['start_date']}..{meta['historical_range']['end_date']}")
PY

echo
echo "== FastAPI design endpoints =="
if curl -fsS http://127.0.0.1:8008/api/stations/current >/tmp/weather_lab_current.json && \
   curl -fsS http://127.0.0.1:8008/api/analysis/summary >/tmp/weather_lab_summary.json && \
   curl -fsS "http://127.0.0.1:8008/api/analysis/trends?metric=temperature&station_id=all" >/tmp/weather_lab_trends.json; then
  python - <<'PY'
import json
current = json.load(open("/tmp/weather_lab_current.json", encoding="utf-8"))
summary = json.load(open("/tmp/weather_lab_summary.json", encoding="utf-8"))
trends = json.load(open("/tmp/weather_lab_trends.json", encoding="utf-8"))
print(f"api_current={len(current)}")
print(f"api_summary={[(item['station_id'], item['records']) for item in summary]}")
print(f"api_trend_stations={list(trends['series'])}")
PY
else
  echo "FastAPI is not running on http://127.0.0.1:8008"
fi

echo
echo "== HDFS and Spark outputs =="
./scripts/distro-bigdata.sh "hdfs dfs -ls /weathertextdb; hdfs dfs -ls /weather_analysis; hdfs dfs -cat /weather_analysis/summary/part-* | sed -n '1,5p'"

echo
echo "== HBase current table =="
tmp_hbase_script="/tmp/weather_lab_hbase_scan.hbase"
cat > "$tmp_hbase_script" <<'HBASE'
scan 'realtime_weather', {LIMIT => 10}
exit
HBASE
./scripts/distro-bigdata.sh "hbase shell -n $tmp_hbase_script"
