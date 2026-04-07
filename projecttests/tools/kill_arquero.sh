#!/usr/bin/env bash
# Kill any process listening on the Arquero API port (default: 3336).
PORT="${ARQUERO_PORT:-3336}"
PIDS="$(lsof -ti:"$PORT" 2>/dev/null)"
if [ -n "$PIDS" ]; then
  echo "Killing process(es) on port $PORT: $PIDS"
  echo "$PIDS" | xargs kill 2>/dev/null || true
else
  echo "No process on port $PORT"
fi
