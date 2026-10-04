#!/bin/sh
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Python 3 is required: https://www.python.org/downloads/"; exit 1; }
command -v claude >/dev/null || echo "Warning: Claude Code not found, AI features will be disabled."
PORT=${PORT:-8765}
while lsof -i ":$PORT" >/dev/null 2>&1; do PORT=$((PORT + 1)); done
(sleep 1 && open "http://localhost:$PORT" 2>/dev/null || xdg-open "http://localhost:$PORT" 2>/dev/null) &
exec python3 server.py "$PORT"
