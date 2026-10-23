#!/usr/bin/env bash
# Start the API (:5001) and the GUI (:3020), then open the GUI in the browser.
# Servers that are already running are reused. Ctrl-C stops what this started.
# Set NO_OPEN=1 to skip opening the browser.
set -euo pipefail
cd "$(dirname "$0")/.."

API_PORT=5001
UI_PORT=3020
URL="http://localhost:$UI_PORT"
started=0

port_busy() { lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# Kill the whole process group on exit: npm and Flask's debug reloader both
# spawn children that a plain `kill $pid` would orphan.
trap '[ "$started" = 1 ] && kill 0 2>/dev/null' EXIT
trap 'exit 0' INT TERM

if port_busy "$API_PORT"; then
  echo "API already running on :$API_PORT"
else
  echo "Starting API on :$API_PORT"
  uv run api_server.py &
  started=1
fi

if port_busy "$UI_PORT"; then
  echo "GUI already running on :$UI_PORT"
else
  [ -d react_gui/node_modules ] || npm --prefix react_gui install
  echo "Starting GUI on :$UI_PORT"
  # CI=true: react-scripts otherwise exits as soon as stdin closes, which it
  # does immediately for a background job. BROWSER=none: we open it ourselves.
  (cd react_gui && CI=true BROWSER=none npm start) &
  started=1
fi

for _ in $(seq 1 120); do
  curl -sf -o /dev/null "$URL" && break
  sleep 1
done
curl -sf -o /dev/null "$URL" || { echo "GUI did not come up on $URL" >&2; exit 1; }

echo "Nameforge is up: $URL"
[ "${NO_OPEN:-}" = 1 ] || open "$URL"

if [ "$started" = 1 ]; then
  echo "Ctrl-C to stop."
  wait
fi
