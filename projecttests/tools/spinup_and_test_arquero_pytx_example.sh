#!/usr/bin/env bash
# Start the arquero_pytx_example FastAPI skeleton, run the integration
# test suite against it, then stop the server.
#
# arquero_pytx_example is a handwritten FastAPI implementation that
# demonstrates how a translated Python Arquero API should respond to the
# integration test suite. It is the reference example for what a complete
# tt-translated project should produce.
#
# Usage:
#   bash projecttests/tools/spinup_and_test_arquero_pytx_example.sh [pytest-args...]
#
# Options (env vars):
#   ARQUERO_PYTX_EXAMPLE_PORT   Host port to bind (default: 3337)
#   KEEP_UP                     Set to 1 to leave the server running after tests
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTX_DIR="$ROOT_DIR/translations/arquero_pytx_example"
PORT="${ARQUERO_PYTX_EXAMPLE_PORT:-3337}"
API_URL="http://localhost:$PORT"

# ---------------------------------------------------------------------------
# Resolve uv
# ---------------------------------------------------------------------------
UV="uv"
if ! command -v uv &>/dev/null; then
  echo "ERROR: 'uv' not found. Install it from https://github.com/astral-sh/uv" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Sync Python deps for the skeleton project
# ---------------------------------------------------------------------------
"$UV" sync --project "$PYTX_DIR" --extra dev --quiet

# ---------------------------------------------------------------------------
# Start the FastAPI skeleton in the background
# ---------------------------------------------------------------------------
echo "Starting arquero_pytx_example skeleton (port $PORT)..."
(cd "$PYTX_DIR" && "$UV" run python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port "$PORT" \
  --log-level warning) \
  &
SERVER_PID=$!

stop_server() {
  if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
  fi
}
trap stop_server EXIT

# ---------------------------------------------------------------------------
# Wait for the server to be ready
# ---------------------------------------------------------------------------
echo "Waiting for API to be ready..."
for i in $(seq 1 30); do
  if curl -sf "$API_URL/health" > /dev/null 2>&1; then
    echo "API is up."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: API did not become healthy after 30 s" >&2
    exit 1
  fi
  sleep 1
done

# ---------------------------------------------------------------------------
# Run the tests
# ---------------------------------------------------------------------------
EXIT_CODE=0
ARQUERO_API_URL="$API_URL" \
  "$UV" run --project "$ROOT_DIR/tt" pytest "$ROOT_DIR/projecttests/arquero_api" -v "$@" \
  || EXIT_CODE=$?

# ---------------------------------------------------------------------------
# Tear down
# ---------------------------------------------------------------------------
if [ "${KEEP_UP:-0}" != "1" ]; then
  echo "Stopping arquero_pytx_example server..."
  stop_server
fi

exit $EXIT_CODE
