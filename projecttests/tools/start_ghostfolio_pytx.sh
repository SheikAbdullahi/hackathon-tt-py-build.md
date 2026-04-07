#!/usr/bin/env bash
# start_ghostfolio_pytx.sh — Start the tt-translated ghostfolio_pytx FastAPI server
# and wait until it is healthy. Does NOT run any tests.
#
# Usage:
#   bash projecttests/tools/start_ghostfolio_pytx.sh
#
# Options (env vars):
#   PYTX_PORT   Port to bind (default: 3335)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTX_DIR="$ROOT_DIR/translations/ghostfolio_pytx"
PORT="${PYTX_PORT:-3335}"
API_URL="http://localhost:$PORT"
UV="uv"

"$UV" sync --project "$PYTX_DIR" --extra dev --quiet

echo "Starting ghostfolio_pytx (port $PORT)..."
(cd "$PYTX_DIR" && "$UV" run python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port "$PORT" \
  --log-level warning) &

echo "Waiting for API to be ready..."
for i in $(seq 1 30); do
  if curl -sf "$API_URL/api/v1/health" > /dev/null 2>&1; then
    echo "API is up."
    exit 0
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: API did not become healthy after 30 s" >&2
    exit 1
  fi
  sleep 1
done
