#!/usr/bin/env bash
# detect_rule_breaches.sh — Run all implementation-rule detection scripts.
#
# Exits non-zero if any rule is breached.
#
# Usage:
#   bash evaluate/checks/detect_rule_breaches.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
RULES_DIR="$SCRIPT_DIR/implementation_rules"

FAILURES=0

for script in "$RULES_DIR"/detect_*.py; do
  name="$(basename "$script" .py)"
  # Skip LLM review if no API key
  if [[ "$name" == "detect_explicit_implementation_llm" ]] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "SKIP: $name (no ANTHROPIC_API_KEY)"
    continue
  fi
  echo -n "CHECK: $name ... "
  if uv run --project "$ROOT_DIR/tt" python "$script" > /dev/null 2>&1; then
    echo "OK"
  else
    echo "FAIL"
    uv run --project "$ROOT_DIR/tt" python "$script" 2>&1 | sed 's/^/  /'
    FAILURES=$((FAILURES + 1))
  fi
done

if [ "$FAILURES" -gt 0 ]; then
  echo ""
  echo "$FAILURES rule breach(es) detected."
  exit 1
else
  echo ""
  echo "All implementation rules OK."
fi
