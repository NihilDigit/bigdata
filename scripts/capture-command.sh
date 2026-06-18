#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <label> <command>" >&2
  exit 2
fi

label="$1"
shift
cmd="$*"

source "$(dirname "${BASH_SOURCE[0]}")/bigdata-env.sh"
mkdir -p "$WEATHER_REPORT_ASSETS"

log_path="$WEATHER_REPORT_ASSETS/${label}.log"
png_path="$WEATHER_REPORT_ASSETS/${label}.png"

set +e
{
  echo "$ $cmd"
  echo
  bash -lc "source '$WEATHER_PROJECT_ROOT/scripts/bigdata-env.sh'; $cmd"
} 2>&1 | tee "$log_path"
status=${PIPESTATUS[0]}
set -e

python "$WEATHER_PROJECT_ROOT/scripts/render-log-image.py" "$log_path" "$png_path"
echo "Rendered $png_path"
exit "$status"
