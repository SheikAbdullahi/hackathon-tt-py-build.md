#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
TRANSLATION_DIR="$ROOT_DIR/translations/arquero_pytx"

if [ ! -d "$TRANSLATION_DIR" ]; then
  echo "Error: translated project not found at $TRANSLATION_DIR" >&2
  exit 1
fi

echo "Running arquero API tests in $TRANSLATION_DIR"
exec uv run --project "$ROOT_DIR/tt" pytest "$TRANSLATION_DIR" -v "$@"
