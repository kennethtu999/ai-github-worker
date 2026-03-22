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

: "${CONTAINER_NAME:?CONTAINER_NAME is required}"

if podman ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
  echo "Stopping running container $CONTAINER_NAME ..."
  podman stop "$CONTAINER_NAME"
fi

if podman ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
  echo "Removing container $CONTAINER_NAME ..."
  podman rm "$CONTAINER_NAME"
else
  echo "Container $CONTAINER_NAME does not exist."
fi
