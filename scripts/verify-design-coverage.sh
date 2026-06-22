#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "== Required implementation entries =="
test -f backend/scripts/weather_dataserver.py
test -f scripts/upload-esp32-weatherstation.sh
test -f scripts/create-hive-weather-table.sh
test -f scripts/run-spark-analysis-yarn.sh
test -x scripts/upload-esp32-weatherstation.sh
test -x scripts/create-hive-weather-table.sh
test -x scripts/run-spark-analysis-yarn.sh
echo "entrypoints=ok"

echo
echo "== Python syntax =="
python -m py_compile \
  backend/app.py \
  backend/scripts/weather_dataserver.py \
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
grep -q '^PORT = 8080$' esp32/weatherstation_main.py
echo "esp32=ok"

echo
echo "== HBase TTL script =="
tmp_hbase="/tmp/weather_lab_verify_hbase.hbase"
python backend/scripts/build_hbase_current_script.py \
  data/raw/current_weather_combined.csv \
  "$tmp_hbase" >/tmp/weather_lab_verify_hbase.log
grep -q "TTL => 150" "$tmp_hbase"
grep -q "happybase.Connection" backend/app.py
echo "hbase_ttl=ok"

echo
echo "== Spark design flags =="
grep -q "enableHiveSupport" backend/scripts/spark_weather_analysis.py
grep -q "window_seconds" backend/scripts/spark_weather_analysis.py
grep -q "/weather_10secmean" backend/scripts/spark_weather_analysis.py
grep -q -- "--source hive" scripts/run-spark-analysis-yarn.sh
grep -q -- "--master yarn" scripts/run-spark-analysis-yarn.sh
echo "spark=ok"
