#!/usr/bin/env bash
# coverage_ghostfolio_integration.sh — TypeScript coverage for the Ghostfolio API
# driven by the Python integration test suite.
#
# What it does:
#   1. Builds Ghostfolio from source (with source maps, no minification)
#   2. Builds a minimal Docker image instrumented with NODE_V8_COVERAGE
#   3. Starts the full Docker stack (Postgres + Redis + yahoo-mock + coverage image)
#   4. Runs the Python integration test suite against the live API
#   5. Gracefully stops the server so V8 flushes all coverage data
#   6. Runs `c8 report` inside a container (paths match the running image)
#      to produce HTML + lcov + text reports mapped back to TypeScript source
#   7. Tears down the stack
#
# Output:
#   coverage/ghostfolio-integration/html/index.html  — browsable HTML report
#   coverage/ghostfolio-integration/lcov.info        — machine-readable lcov
#
# Usage:
#   bash projecttests/tools/coverage_ghostfolio_integration.sh
#   KEEP_UP=1 bash projecttests/tools/coverage_ghostfolio_integration.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
GF_DIR="$ROOT_DIR/projects/ghostfolio"
GF_DOCKER_DIR="$GF_DIR/docker"
COVERAGE_DIR="$ROOT_DIR/coverage/ghostfolio-integration"
REPORT_DIR="$COVERAGE_DIR/html"

mkdir -p "$COVERAGE_DIR" "$REPORT_DIR"

# ---------------------------------------------------------------------------
# Ensure .env exists (same values as spinup_and_test_ghostfolio.sh)
# ---------------------------------------------------------------------------
ENV_FILE="$GF_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "Creating test .env ..."
  cat > "$ENV_FILE" <<'EOF'
COMPOSE_PROJECT_NAME=ghostfolio
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=ghostfolio_password
POSTGRES_DB=ghostfolio-db
POSTGRES_USER=user
POSTGRES_PASSWORD=ghostfolio_password
ACCESS_TOKEN_SALT=accesstokensalt
DATABASE_URL=postgresql://user:ghostfolio_password@postgres:5432/ghostfolio-db?connect_timeout=300&sslmode=prefer
JWT_SECRET_KEY=jwtsecretkey
EOF
fi

cd "$GF_DIR"

# ---------------------------------------------------------------------------
# 1. Build TypeScript → dist/apps/api/ with source maps, no minification
# ---------------------------------------------------------------------------
echo "=== [1/6] Build Ghostfolio TypeScript (source maps, no minification) ==="
npx nx build api --generatePackageJson=true --optimization=false

# ---------------------------------------------------------------------------
# 2. Build coverage Docker image
# ---------------------------------------------------------------------------
echo "=== [2/6] Build coverage Docker image ==="
cd "$GF_DOCKER_DIR"
docker compose \
  -f docker-compose.yml \
  -f docker-compose.test.yml \
  -f docker-compose.coverage.yml \
  build ghostfolio

# ---------------------------------------------------------------------------
# 3. Start the full stack
# ---------------------------------------------------------------------------
echo "=== [3/6] Start Docker stack ==="
docker compose \
  -f docker-compose.yml \
  -f docker-compose.test.yml \
  -f docker-compose.coverage.yml \
  up -d

echo "Waiting for API to be ready ..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:3333/api/v1/health >/dev/null 2>&1; then
    echo "API is up."
    break
  fi
  sleep 2
done
curl -sf http://localhost:3333/api/v1/health >/dev/null || { echo "ERROR: API did not come up in time"; exit 1; }

# ---------------------------------------------------------------------------
# 4. Run Python integration tests
# ---------------------------------------------------------------------------
echo "=== [4/6] Run integration tests ==="
cd "$ROOT_DIR"
uv sync --project tt --extra dev
TEST_EXIT=0
GHOSTFOLIO_API_URL=http://localhost:3333 \
  uv run --project tt pytest projecttests/ghostfolio_api -v --tb=short \
  || TEST_EXIT=$?

# ---------------------------------------------------------------------------
# 5. Graceful stop → V8 flushes coverage JSON to /coverage volume
# ---------------------------------------------------------------------------
echo "=== [5/6] Stop server (flushing V8 coverage) ==="
docker stop ghostfolio 2>/dev/null || true

# ---------------------------------------------------------------------------
# 6. Generate HTML + lcov + text report via c8 inside a sibling container.
#    Mount points replicate the paths the running server saw:
#      /app   → dist/apps/api/   (compiled JS + source maps)
#      /apps  → apps/            (TypeScript source, for --src and --all)
#      /coverage → v8_coverage volume
#      /report   → coverage/ghostfolio-integration/html  (output)
# ---------------------------------------------------------------------------
echo "=== [6/6] Generate coverage report ==="
docker run --rm \
  -v ghostfolio_v8_coverage:/coverage \
  -v "$GF_DIR/dist/apps/api:/app" \
  -v "$GF_DIR/apps:/apps" \
  -v "$REPORT_DIR:/report" \
  -w /app \
  node:20-alpine \
  sh -c "
    npm install --silent c8 2>/dev/null
    npx c8 report \
      --reporter=html \
      --reporter=text \
      --reporter=lcov \
      --temp-directory=/coverage \
      --output-dir=/report \
      --src=/apps/api/src \
      --all \
      --include='**/*.ts' \
      --exclude='**/*.spec.ts' \
      --exclude='**/node_modules/**'
  "

# Copy lcov.info to root coverage dir for easy access
cp "$REPORT_DIR/lcov.info" "$COVERAGE_DIR/lcov.info" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Tear down (unless KEEP_UP=1)
# ---------------------------------------------------------------------------
if [ "${KEEP_UP:-0}" != "1" ]; then
  echo "Tearing down Docker stack ..."
  cd "$GF_DOCKER_DIR"
  docker compose \
    -f docker-compose.yml \
    -f docker-compose.test.yml \
    -f docker-compose.coverage.yml \
    down -v
fi

echo ""
echo "============================================================"
echo "  Coverage report: $REPORT_DIR/index.html"
echo "  lcov:            $COVERAGE_DIR/lcov.info"
echo "============================================================"

if [ "$TEST_EXIT" != "0" ]; then
  echo "WARNING: $TEST_EXIT test(s) failed"
  exit "$TEST_EXIT"
fi
