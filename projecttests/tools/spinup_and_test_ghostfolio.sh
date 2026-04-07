#!/usr/bin/env bash
# Spin up the Ghostfolio Node.js backend via Docker Compose, run the API
# integration test suite against it, then tear it down.
#
# Usage:
#   bash projecttests/tools/spinup_and_test_ghostfolio.sh [pytest-args...]
#
# Options (env vars):
#   GHOSTFOLIO_PORT   Host port to expose (default: 3333)
#   KEEP_UP           Set to 1 to leave containers running after tests
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
GF_DIR="$ROOT_DIR/projects/ghostfolio"
COMPOSE_FILE="$GF_DIR/docker/docker-compose.yml"
COMPOSE_TEST_OVERLAY="$GF_DIR/docker/docker-compose.test.yml"
# docker-compose.yml has `env_file: ../.env` baked in, so we must write to .env
ENV_FILE="$GF_DIR/.env"
PORT="${GHOSTFOLIO_PORT:-3333}"
API_URL="http://localhost:$PORT"

# ---------------------------------------------------------------------------
# Generate a test .env if one does not already exist
# ---------------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  echo "Creating $ENV_FILE with test credentials..."
  cat > "$ENV_FILE" <<'EOF'
COMPOSE_PROJECT_NAME=ghostfolio-test

# CACHE
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=testredispassword

# POSTGRES
POSTGRES_DB=ghostfolio-test-db
POSTGRES_USER=testuser
POSTGRES_PASSWORD=testpassword

# VARIOUS
ACCESS_TOKEN_SALT=test-access-token-salt-32chars!!
DATABASE_URL=postgresql://testuser:testpassword@postgres:5432/ghostfolio-test-db?connect_timeout=300&sslmode=prefer
JWT_SECRET_KEY=test-jwt-secret-key-32chars!!!!!
EOF
fi

# ---------------------------------------------------------------------------
# Resolve uv and sync dependencies
# ---------------------------------------------------------------------------
UV="uv"
if ! command -v uv &>/dev/null; then
  echo "ERROR: 'uv' not found. Install it from https://github.com/astral-sh/uv" >&2
  exit 1
fi

# Sync dev dependencies (installs requests etc.) from the tt project
"$UV" sync --project "$ROOT_DIR/tt" --extra dev --quiet

# ---------------------------------------------------------------------------
# Bring up the stack
# ---------------------------------------------------------------------------
echo "Starting Ghostfolio stack (port $PORT)..."
docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_TEST_OVERLAY" -p ghostfolio-test up -d --wait

# Extra wait for the Ghostfolio app itself (compose --wait checks healthchecks,
# but the app may still be running migrations)
echo "Waiting for API to be ready..."
for i in $(seq 1 30); do
  if curl -sf "$API_URL/api/v1/health" > /dev/null 2>&1; then
    echo "API is up."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: API did not become healthy after 60 s" >&2
    docker compose -f "$COMPOSE_FILE" -p ghostfolio-test logs
    exit 1
  fi
  sleep 2
done

# ---------------------------------------------------------------------------
# Run the tests
# ---------------------------------------------------------------------------
EXIT_CODE=0
GHOSTFOLIO_API_URL="$API_URL" \
  "$UV" run --project "$ROOT_DIR/tt" pytest "$ROOT_DIR/projecttests/ghostfolio_api" -v "$@" \
  || EXIT_CODE=$?

# ---------------------------------------------------------------------------
# Tear down (unless KEEP_UP=1)
# ---------------------------------------------------------------------------
if [ "${KEEP_UP:-0}" != "1" ]; then
  echo "Tearing down Ghostfolio stack..."
  docker compose -f "$COMPOSE_FILE" -f "$COMPOSE_TEST_OVERLAY" -p ghostfolio-test down -v --remove-orphans
fi

exit $EXIT_CODE
