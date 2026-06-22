#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$PROJECT_ROOT/scripts/distro-bigdata.sh" "
hive -f '$PROJECT_ROOT/backend/sql/create_weather_table.sql'
"
