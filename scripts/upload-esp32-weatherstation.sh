#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${ESP32_PORT:-/dev/ttyACM0}"
SSID="${ESP32_SSID:?Set ESP32_SSID to the hotspot SSID}"
WIFI_KEY="${ESP32_WIFI_KEY:?Set ESP32_WIFI_KEY to the hotspot password}"
DHT_PIN="${ESP32_DHT_PIN:-4}"
TMP_MAIN="$(mktemp /tmp/weatherstation_main.XXXXXX.py)"

cleanup() {
  rm -f "$TMP_MAIN"
}
trap cleanup EXIT

python - "$PROJECT_ROOT/esp32/weatherstation_main.py" "$TMP_MAIN" "$SSID" "$WIFI_KEY" "$DHT_PIN" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

src, dst, ssid, wifi_key, dht_pin = sys.argv[1:6]
text = Path(src).read_text(encoding="utf-8")
replacements = {
    'SSID = "YOUR_WIFI_SSID"': f'SSID = "{ssid}"',
    'WIFI_KEY = "YOUR_WIFI_KEY"': f'WIFI_KEY = "{wifi_key}"',
    "DHT_PIN = 4": f"DHT_PIN = {int(dht_pin)}",
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"template marker not found: {old}")
    text = text.replace(old, new)
Path(dst).write_text(text, encoding="utf-8")
PY

UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
UV_TOOL_DIR="${UV_TOOL_DIR:-/tmp/uv-tools}" \
uvx mpremote connect "$PORT" fs cp "$TMP_MAIN" :/main.py

UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
UV_TOOL_DIR="${UV_TOOL_DIR:-/tmp/uv-tools}" \
uvx mpremote connect "$PORT" reset

echo "Uploaded weatherstation main.py to $PORT"
