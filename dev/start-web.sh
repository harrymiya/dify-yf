#!/bin/bash
# Start Dify web (frontend) in dev mode.
# If port 3000 is occupied by another project (e.g. dcx-web), fall back to 3001.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
WEB_DIR="$ROOT_DIR/web"

# Determine the port to use.
PORT=3000
if ss -ltn 2>/dev/null | grep -qE "[:.]3000\b"; then
  echo "==> Port 3000 is already in use (likely dcx-web). Falling back to 3001."
  PORT=3001
fi

echo "==> Starting Dify web dev server on :${PORT}..."
cd "$WEB_DIR"
# Disable Turbopack disk-persistent cache. On modest hardware the on-disk cache
# can balloon to tens of GB and trigger long DB compaction passes on cold start,
# stalling HTTP responses for minutes. Keep caching in-memory only (dev is
# E2E-cold-compiled anyway). Overridable via TURBOPACK_CACHE=1.
PORT="$PORT" \
  CONSOLE_API_URL="${CONSOLE_API_URL:-http://localhost:5001}" \
  NEXT_PUBLIC_SOCKET_URL="${NEXT_PUBLIC_SOCKET_URL:-ws://localhost:$PORT}" \
  TURBOPACK_CACHE="${TURBOPACK_CACHE:-0}" \
pnpm exec next dev
