#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "== Required implementation entries =="
test -f backend/scripts/weather_dataserver.py
test -f backend/scripts/openmeteo_station_client.py
test -f scripts/upload-esp32-weatherstation.sh
test -f scripts/create-hive-weather-table.sh
test -f scripts/run-spark-analysis-yarn.sh
test -f frontend/app/analysis/page.tsx
test -x scripts/upload-esp32-weatherstation.sh
test -x scripts/create-hive-weather-table.sh
test -x scripts/run-spark-analysis-yarn.sh
echo "entrypoints=ok"

echo
echo "== Python syntax =="
python -m py_compile \
  backend/app.py \
  backend/scripts/weather_dataserver.py \
  backend/scripts/openmeteo_station_client.py \
  backend/scripts/fetch_open_meteo.py \
  backend/scripts/spark_weather_analysis.py \
  backend/scripts/build_hbase_current_script.py \
  backend/scripts/merge_current_weather.py
echo "python=ok"

echo
echo "== Shell syntax =="
bash -n scripts/upload-esp32-weatherstation.sh
bash -n scripts/create-hive-weather-table.sh
bash -n scripts/run-spark-analysis-yarn.sh
bash -n scripts/verify-design-coverage.sh
echo "shell=ok"

echo
echo "== ESP32 defaults =="
grep -q '^DHT_PIN = 4$' esp32/weatherstation_main.py
grep -q '^DHT_PIN = 4$' esp32/usb_weatherstation_main.py
grep -q '^SERVER_PORT = 8080$' esp32/weatherstation_main.py
grep -q 'Sec-WebSocket-Version: 13' esp32/weatherstation_main.py
echo "esp32=ok"

echo
echo "== HBase TTL script =="
tmp_hbase="/tmp/weather_lab_verify_hbase.hbase"
python backend/scripts/build_hbase_current_script.py \
  data/raw/current_weather_combined.csv \
  "$tmp_hbase" >/tmp/weather_lab_verify_hbase.log
grep -q "TTL => 150" "$tmp_hbase"
grep -q "happybase.Connection" backend/app.py
grep -q "hbase_current_by_station()" backend/app.py
echo "hbase_ttl=ok"

echo
echo "== Spark design flags =="
grep -q "enableHiveSupport" backend/scripts/spark_weather_analysis.py
grep -q "window_seconds" backend/scripts/spark_weather_analysis.py
grep -q "/weather_10secmean" backend/scripts/spark_weather_analysis.py
grep -q "pressure_delta" backend/scripts/spark_weather_analysis.py
grep -q "max_wind_speed" backend/scripts/spark_weather_analysis.py
grep -q "atan2" backend/scripts/spark_weather_analysis.py
grep -q -- "--source hive" scripts/run-spark-analysis-yarn.sh
grep -q -- "--master yarn" scripts/run-spark-analysis-yarn.sh
echo "spark=ok"

echo
echo "== Frontend design shape =="
grep -q 'view="analysis"' frontend/app/analysis/page.tsx
grep -q '对比分析' frontend/components/weather-dashboard.tsx
grep -q 'HBase scan 最近 150s' frontend/components/weather-dashboard.tsx
grep -q 'Spark 预计算结果' frontend/components/weather-dashboard.tsx
! grep -q 'ESP32 实时采样' frontend/components/weather-dashboard.tsx
! grep -q 'live-panel' frontend/app/globals.css
echo "frontend=ok"
