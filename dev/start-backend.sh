#!/bin/bash
# Start Dify backend (api) in dev mode, with middleware up.
set -euo pipefail

# uv (and other tooling) live outside the default PATH for non-login shells.
export PATH="/mnt/data/.hermes/bin:$PATH"

# The global ALL_PROXY points to a socks:// proxy (socks://127.0.0.1:7890) which
# breaks httpx in the API. Unset it before starting (same as the original dev cmd).
export -n ALL_PROXY all_proxy
export ALL_PROXY= all_proxy=

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$ROOT_DIR/docker"
API_DIR="$ROOT_DIR/api"

echo "==> [1/3] Ensuring middleware (postgres/redis/weaviate/plugin_daemon) is up..."
if [ ! -f "$DOCKER_DIR/middleware.env" ]; then
  echo "ERROR: $DOCKER_DIR/middleware.env missing."
  echo "       Copy it from an example or create it (see repo docs) before starting the backend."
  exit 1
fi
cd "$DOCKER_DIR"
docker compose -f docker-compose.middleware.yaml --env-file middleware.env -p docker up -d --no-recreate \
  db_postgres redis weaviate plugin_daemon

echo "==> [2/3] Waiting for plugin daemon (port 5002) to be ready..."
for i in $(seq 1 20); do
  if curl -s -o /dev/null "http://127.0.0.1:5002/health" 2>/dev/null; then
    break
  fi
  sleep 1
done
echo "    (plugin daemon container status: $(docker ps --filter name=plugin_daemon --format '{{.Status}}'))"

echo "==> [3/3] Running DB migrations + starting API on :5001..."
cd "$API_DIR"
uv run flask db upgrade
uv run python -m app
