#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
uvx --with fastapi --with uvicorn uvicorn backend.app:app --host 127.0.0.1 --port "${PORT:-8008}"
