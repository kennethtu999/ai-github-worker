#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT_DIR/local.env"

if ! command -v podman >/dev/null 2>&1; then
  echo "podman is required but not installed."
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "local.env not found. Copy local.env.example to local.env and fill it first."
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

: "${IMAGE_NAME:?IMAGE_NAME is required}"
: "${CONTAINER_NAME:?CONTAINER_NAME is required}"
: "${HOST_PORT:?HOST_PORT is required}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
: "${GITHUB_WEBHOOK_SECRET:?GITHUB_WEBHOOK_SECRET is required}"

mkdir -p "$ROOT_DIR/data" "$ROOT_DIR/repos"

if [ ! -d "$CODEX_AUTH_DIR" ]; then
  if [ -n "${CODEX_API_KEY:-}" ]; then
    mkdir -p "$CODEX_AUTH_DIR"
  else
    echo "Codex auth dir not found: $CODEX_AUTH_DIR"
    echo "Run codex login on host first, or set CODEX_API_KEY in local.env."
    exit 1
  fi
fi

echo "Building image $IMAGE_NAME ..."
podman build -t "$IMAGE_NAME" "$ROOT_DIR"

if podman ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
  echo "Container $CONTAINER_NAME is already running."
  exit 0
fi

if podman ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
  echo "Starting existing container $CONTAINER_NAME ..."
  podman start "$CONTAINER_NAME"
  exit 0
fi

echo "Creating container $CONTAINER_NAME ..."
podman run -d \
  --name "$CONTAINER_NAME" \
  -p "$HOST_PORT:8080" \
  -v "$ROOT_DIR/data:/app/data" \
  -v "$ROOT_DIR/repos:/app/repos" \
  -v "$CODEX_AUTH_DIR:/root/.codex" \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -e GITHUB_WEBHOOK_SECRET="$GITHUB_WEBHOOK_SECRET" \
  -e CODEX_API_KEY="${CODEX_API_KEY:-}" \
  -e WORKER_DRY_RUN="${WORKER_DRY_RUN:-false}" \
  -e WEBHOOK_HOST="${WEBHOOK_HOST:-0.0.0.0}" \
  -e WEBHOOK_PORT="${WEBHOOK_PORT:-8080}" \
  -e SCHEDULER_INTERVAL_SECONDS="${SCHEDULER_INTERVAL_SECONDS:-5}" \
  -e DEFAULT_BASE_BRANCH="${DEFAULT_BASE_BRANCH:-main}" \
  "$IMAGE_NAME"

echo "Started $CONTAINER_NAME on http://localhost:$HOST_PORT"
