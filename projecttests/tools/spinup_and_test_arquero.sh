#!/usr/bin/env bash
# Start the Arquero API server, run integration tests against it, then stop it.
#
# Usage:
#   bash projecttests/tools/spinup_and_test_arquero.sh [pytest-args...]
#
# Options (env vars):
#   ARQUERO_PORT   Host port to bind (default: 3336)
#   KEEP_UP        Set to 1 to leave the server running after tests
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
API_DIR="$ROOT_DIR/projects/arquero/api"
PORT="${ARQUERO_PORT:-3336}"
API_URL="http://localhost:$PORT"

UV="uv"
if ! command -v uv &>/dev/null; then
  echo "ERROR: 'uv' not found." >&2
  exit 1
fi

if ! command -v node &>/dev/null; then
  echo "ERROR: 'node' not found. Install Node.js to run the Arquero API server." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Install npm deps if needed (arquero root first, then api)
# ---------------------------------------------------------------------------
if [ ! -d "$ROOT_DIR/projects/arquero/node_modules" ]; then
  echo "Installing Arquero library dependencies..."
  npm install --prefix "$ROOT_DIR/projects/arquero" --silent
fi
if [ ! -d "$API_DIR/node_modules" ]; then
  echo "Installing Arquero API dependencies..."
  npm install --prefix "$API_DIR" --silent
fi

# ---------------------------------------------------------------------------
# Start the API server in the background
# ---------------------------------------------------------------------------
echo "Starting Arquero API (port $PORT)..."
ARQUERO_PORT="$PORT" node "$API_DIR/server.mjs" &
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
    echo "ERROR: Arquero API did not become healthy after 30 s" >&2
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
  echo "Stopping Arquero API server..."
  stop_server
fi

exit $EXIT_CODE
