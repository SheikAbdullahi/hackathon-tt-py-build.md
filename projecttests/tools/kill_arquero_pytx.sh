#!/usr/bin/env bash
# Kill any process listening on the arquero_pytx port (default: 3338).
PORT="${ARQUERO_PYTX_PORT:-3338}"
PIDS="$(lsof -ti:"$PORT" 2>/dev/null)"
if [ -n "$PIDS" ]; then
  echo "Killing process(es) on port $PORT: $PIDS"
  echo "$PIDS" | xargs kill 2>/dev/null || true
else
  echo "No process on port $PORT"
fi
