#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ -n "${ESP32_STATION_HOST:-}" ]]; then
  echo "== ESP32 live ingest =="
  timeout "${ESP32_VERIFY_TIMEOUT:-90s}" python3 backend/scripts/weather_dataserver.py \
    --station-host "$ESP32_STATION_HOST" \
    --station-port "${ESP32_STATION_PORT:-8080}" \
    --max-records "${ESP32_VERIFY_RECORDS:-2}" \
    --flush-size "${ESP32_VERIFY_RECORDS:-2}" \
    --local-out data/raw/live_weather_observations.csv
  echo
fi

echo "== MVP pipeline checks =="
./scripts/verify-mvp.sh

echo
echo "== Design coverage checks =="
./scripts/verify-design-coverage.sh

echo
echo "== Extended API checks =="
curl -fsS http://127.0.0.1:8008/api/stations -o /tmp/weather_lab_stations.json
curl -fsS http://127.0.0.1:8008/api/metrics -o /tmp/weather_lab_metrics.json
curl -fsS "http://127.0.0.1:8008/api/analysis/trends?metric=pressure&station_id=tangshan" -o /tmp/weather_lab_trends.json
curl -fsS "http://127.0.0.1:8008/api/export/weather_observations.csv?station_id=tangshan" -o /tmp/weather_lab_tangshan.csv
curl -fsS "http://127.0.0.1:8008/api/stations/tangshan/live?seconds=300" -o /tmp/weather_lab_tangshan_live.json
python - <<'PY'
import csv
import json

stations = json.load(open("/tmp/weather_lab_stations.json", encoding="utf-8"))
metrics = json.load(open("/tmp/weather_lab_metrics.json", encoding="utf-8"))
trends = json.load(open("/tmp/weather_lab_trends.json", encoding="utf-8"))
rows = list(csv.DictReader(open("/tmp/weather_lab_tangshan.csv", encoding="utf-8")))
live = json.load(open("/tmp/weather_lab_tangshan_live.json", encoding="utf-8"))

print(f"stations={len(stations)}")
print(f"metrics={[item['id'] for item in metrics]}")
print(f"trend_metric={trends['metric']['id']}")
print(f"tangshan_trend_points={len(trends['series']['tangshan'])}")
print(f"tangshan_export_rows={len(rows)}")
print(f"tangshan_live_rows={len(live)}")

assert len(stations) == 3
assert len(metrics) == 5
assert trends["metric"]["id"] == "pressure"
assert len(trends["series"]["tangshan"]) == 168
assert len(rows) == 168
assert len(live) > 0
assert live[-1]["station_id"] == "tangshan"
PY

echo
echo "== Frontend checks =="
uvx --with playwright python - <<'PY'
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path.cwd()
chrome_env = os.environ.get("PLAYWRIGHT_CHROME")
if chrome_env:
    chrome = Path(chrome_env)
else:
    candidates = sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"))
    system_candidates = [Path("/usr/bin/google-chrome-stable"), Path("/usr/bin/chromium")]
    chrome = candidates[-1] if candidates else next((path for path in system_candidates if path.exists()), None)
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=str(chrome) if chrome else None)
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.goto("http://127.0.0.1:3000", wait_until="domcontentloaded")
    page.wait_for_selector(".station-marker", state="attached")
    page.wait_for_selector(".live-panel", state="attached")
    overview_tabs = page.locator(".tab-link").count()
    station_markers = page.locator(".station-marker").count()
    live_panel = page.locator(".live-panel").count()
    page.click('a[href="/detail"]')
    page.wait_for_timeout(250)
    page.select_option('select', "tangshan")
    page.locator('select').nth(1).select_option("pressure")
    page.wait_for_timeout(250)
    charts = page.locator(".recharts-wrapper").count()
    live_records = page.locator(".live-record").count()
    records = page.locator("tbody tr").count()
    browser.close()

print(f"tabs={overview_tabs}")
print(f"station_markers={station_markers}")
print(f"live_panel={live_panel}")
print(f"charts={charts}")
print(f"live_records={live_records}")
print(f"records={records}")
print(f"console_errors={errors}")

assert overview_tabs == 2
assert station_markers == 3
assert live_panel == 1
assert charts == 3
assert live_records > 0
assert records == 48
assert not errors
PY
