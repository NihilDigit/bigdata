#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
api_port="${API_PORT:-8008}"
web_port="${PORT:-3000}"

UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uvx --with fastapi --with uvicorn --with happybase uvicorn backend.app:app --host 127.0.0.1 --port "$api_port" &
api_pid=$!

cleanup() {
  kill "$api_pid" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd frontend
API_BASE="http://127.0.0.1:$api_port" bun run dev -- --hostname 127.0.0.1 --port "$web_port"
