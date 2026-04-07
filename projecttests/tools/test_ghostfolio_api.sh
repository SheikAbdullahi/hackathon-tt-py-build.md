#!/usr/bin/env bash
# Run the Python API integration test suite against a live Ghostfolio instance.
#
# Usage:
#   bash projecttests/tools/test_ghostfolio_api.sh [pytest-args...]
#
# Environment variables:
#   GHOSTFOLIO_API_URL   Base URL of the Ghostfolio API (default: http://localhost:3333)
#
# Prerequisites:
#   A running Ghostfolio instance with user signup enabled.
#   See projects/ghostfolio/docker/docker-compose.yml to spin one up.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_DIR="$ROOT_DIR/projecttests/ghostfolio_api"

echo "Running Ghostfolio API tests against ${GHOSTFOLIO_API_URL:-http://localhost:3333}"
exec uv run --project "$ROOT_DIR/tt" pytest "$TEST_DIR" -v "$@"
