#!/usr/bin/env bash
set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSET_DIR="$PROJECT_ROOT/reports/assets"
FIRMWARE="${FIRMWARE:-$PROJECT_ROOT/data/firmware/ESP32_GENERIC_C3-20250415-v1.25.0.bin}"
DEFAULT_PORT="${ESP32_PORT:-/dev/ttyACM0}"
PORT="${1:-$DEFAULT_PORT}"
ESPTOOL_BASE=(uvx esptool --chip esp32c3 --no-stub --port "$PORT")

mkdir -p "$ASSET_DIR"
LOG="$ASSET_DIR/esp32_flash_firmware.log"
PNG="$ASSET_DIR/esp32_flash_firmware.png"

run_flash() {
  set -euo pipefail

  echo "Project: $PROJECT_ROOT"
  echo "Firmware: $FIRMWARE"
  echo "Requested port: $PORT"

  if [[ ! -f "$FIRMWARE" ]]; then
    echo "Firmware file not found: $FIRMWARE" >&2
    exit 1
  fi

  if [[ ! -e "$PORT" ]]; then
    echo "Port not found: $PORT" >&2
    echo "Available serial devices:"
    ls -l /dev/ttyACM* /dev/ttyUSB* /dev/serial/by-id/* 2>/dev/null || true
    exit 1
  fi

  real_port="$(realpath -e "$PORT")"
  echo "Resolved port: $real_port"
  ls -l "$real_port"

  echo
  echo "Checking temporary serial permission"
  if [[ -w "$real_port" ]]; then
    echo "Serial port is writable by current user."
  else
    echo "Serial port is not writable; granting temporary permission with sudo."
    sudo chmod a+rw "$real_port"
  fi
  ls -l "$real_port"

  echo
  echo "Checking ESP32-C3 chip"
  "${ESPTOOL_BASE[@]}" chip-id

  echo
  echo "Erasing flash region"
  "${ESPTOOL_BASE[@]}" erase-region 0x0 0x400000

  echo
  echo "Writing MicroPython firmware"
  "${ESPTOOL_BASE[@]}" --baud 115200 write-flash -z 0x0 "$FIRMWARE"

  echo
  echo "Resetting board"
  "${ESPTOOL_BASE[@]}" run || true

  echo
  echo "ESP32-C3 MicroPython firmware flashing completed."
}

{
  echo "$ scripts/flash-esp32-firmware.sh ${1:-}"
  echo
  run_flash
} 2>&1 | tee "$LOG"
status=${PIPESTATUS[0]}

python "$PROJECT_ROOT/scripts/render-log-image.py" "$LOG" "$PNG" || true
echo "Rendered $PNG"
exit "$status"
