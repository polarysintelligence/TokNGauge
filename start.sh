#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

PORT="${TOKNGAUGE_PORT:-8770}"

# Kill anything already listening on our port (best-effort)
kill_port() {
  local port="$1"
  local pids=""
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
  elif command -v fuser >/dev/null 2>&1; then
    pids=$(fuser -n tcp "$port" 2>/dev/null | tr -s ' ' '\n' | grep -E '^[0-9]+$' || true)
  elif command -v ss >/dev/null 2>&1; then
    pids=$(ss -ltnp 2>/dev/null | awk -v p=":$port" '$4 ~ p { print $0 }' \
      | grep -oE 'pid=[0-9]+' | cut -d= -f2 || true)
  fi
  if [ -n "$pids" ]; then
    echo "Freeing port $port (killing: $pids)"
    for pid in $pids; do kill "$pid" 2>/dev/null || true; done
    sleep 1
    for pid in $pids; do kill -9 "$pid" 2>/dev/null || true; done
  fi
}

kill_port "$PORT"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Start the server
echo "Starting TokNGauge on http://localhost:${PORT} ..."
TOKNGAUGE_PORT="$PORT" python server.py
