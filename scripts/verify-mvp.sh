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
echo "== FastAPI dashboard =="
if curl -fsS http://127.0.0.1:8008/api/dashboard >/tmp/weather_lab_dashboard.json; then
  python - <<'PY'
import json
data = json.load(open("/tmp/weather_lab_dashboard.json", encoding="utf-8"))
print(f"api_current={len(data['current'])}")
print(f"api_hourly={len(data['hourly'])}")
print(f"api_summary={[(item['station_id'], item['records']) for item in data['summary']]}")
PY
else
  echo "FastAPI is not running on http://127.0.0.1:8008"
fi

echo
echo "== HDFS and Spark outputs =="
./scripts/distro-bigdata.sh "hdfs dfs -ls /weather_lab/weathertextdb; hdfs dfs -ls /weather_analysis; hdfs dfs -cat /weather_analysis/station_summary/part-* | sed -n '1,5p'"

echo
echo "== HBase current table =="
tmp_hbase_script="/tmp/weather_lab_hbase_scan.hbase"
cat > "$tmp_hbase_script" <<'HBASE'
scan 'weather_current', {LIMIT => 10}
exit
HBASE
./scripts/distro-bigdata.sh "hbase shell -n $tmp_hbase_script"
