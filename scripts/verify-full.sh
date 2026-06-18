#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "== MVP pipeline checks =="
./scripts/verify-mvp.sh

echo
echo "== Extended API checks =="
curl -fsS http://127.0.0.1:8008/api/stations -o /tmp/weather_lab_stations.json
curl -fsS http://127.0.0.1:8008/api/metrics -o /tmp/weather_lab_metrics.json
curl -fsS "http://127.0.0.1:8008/api/trends?metric=pressure&station_id=tangshan" -o /tmp/weather_lab_trends.json
curl -fsS "http://127.0.0.1:8008/api/export/weather_observations.csv?station_id=tangshan" -o /tmp/weather_lab_tangshan.csv
python - <<'PY'
import csv
import json

stations = json.load(open("/tmp/weather_lab_stations.json", encoding="utf-8"))
metrics = json.load(open("/tmp/weather_lab_metrics.json", encoding="utf-8"))
trends = json.load(open("/tmp/weather_lab_trends.json", encoding="utf-8"))
rows = list(csv.DictReader(open("/tmp/weather_lab_tangshan.csv", encoding="utf-8")))

print(f"stations={len(stations)}")
print(f"metrics={[item['id'] for item in metrics]}")
print(f"trend_metric={trends['metric']['id']}")
print(f"tangshan_trend_points={len(trends['series']['tangshan'])}")
print(f"tangshan_export_rows={len(rows)}")

assert len(stations) == 3
assert len(metrics) == 5
assert trends["metric"]["id"] == "pressure"
assert len(trends["series"]["tangshan"]) == 168
assert len(rows) == 168
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
    chrome = candidates[-1] if candidates else None
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=str(chrome) if chrome else None)
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.goto("http://127.0.0.1:8008", wait_until="networkidle")
    overview_tabs = page.locator(".tab").count()
    station_rows = page.locator(".station-row").count()
    page.click('[data-view="detail"]')
    page.wait_for_timeout(250)
    page.select_option("#metricSelect", "pressure")
    records = page.locator("#recordsBody tr").count()
    page.click('[data-view="system"]')
    page.wait_for_timeout(250)
    pipeline = page.locator(".pipeline-step").count()
    files = page.locator("#filesBody tr").count()
    browser.close()

print(f"tabs={overview_tabs}")
print(f"station_rows={station_rows}")
print(f"records={records}")
print(f"pipeline_steps={pipeline}")
print(f"generated_files={files}")
print(f"console_errors={errors}")

assert overview_tabs == 3
assert station_rows == 3
assert records == 48
assert pipeline == 7
assert files == 8
assert not errors
PY
