#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_CONTAINER_NAME="ai-github-worker-mvp"
DEFAULT_LOG_DIR="/data/ai-github-worker/data/worker_logs"
FALLBACK_LOG_DIR="$ROOT_DIR/data/worker_logs"
DEFAULT_CLONE_KEY="/home/ubuntu/.ssh/gibuicomponent"
DEFAULT_CLONE_REPO="git@github.ibm.com:MEGA-GEB/gib-ui-component.git"

print_menu() {
  cat <<'EOF'
==============================
 AI GitHub Worker Command Menu
==============================
1) 重新部署新版 (destroy -> prune -> pull -> create)
2) 查看容器 Log (podman logs -f)
3) 追蹤最新 worker log
4) Clone gib-ui-component (固定 ssh key)
0) 離開
EOF
}

resolve_container_name() {
  local env_file="$ROOT_DIR/local.env"
  local container_name="$DEFAULT_CONTAINER_NAME"

  if [[ -f "$env_file" ]]; then
    # Read CONTAINER_NAME from local.env if available, without sourcing full file.
    local from_env
    from_env="$(grep -E '^CONTAINER_NAME=' "$env_file" | head -n 1 | cut -d '=' -f2- || true)"
    from_env="${from_env%\"}"
    from_env="${from_env#\"}"
    if [[ -n "$from_env" ]]; then
      container_name="$from_env"
    fi
  fi

  echo "$container_name"
}

run_choice() {
  local choice="$1"

  case "$choice" in
    1)
      cd "$ROOT_DIR"
      ./destroy.sh && podman image prune -f && git pull && ./create.sh
      ;;
    2)
      local container_name
      container_name="$(resolve_container_name)"
      podman logs -f "$container_name"
      ;;
    3)
      local log_dir="$DEFAULT_LOG_DIR"
      if [[ ! -d "$log_dir" ]]; then
        log_dir="$FALLBACK_LOG_DIR"
      fi

      if [[ ! -d "$log_dir" ]]; then
        echo "找不到 log 目錄: $DEFAULT_LOG_DIR 或 $FALLBACK_LOG_DIR"
        exit 1
      fi

      local latest_log
      latest_log="$(ls -t "$log_dir"/*.log 2>/dev/null | head -n 1 || true)"
      if [[ -z "$latest_log" ]]; then
        echo "找不到任何 .log 檔案於 $log_dir"
        exit 1
      fi

      tail -f "$latest_log"
      ;;
    4)
      GIT_SSH_COMMAND="ssh -i $DEFAULT_CLONE_KEY" git clone "$DEFAULT_CLONE_REPO"
      ;;
    0)
      echo "Bye"
      ;;
    *)
      echo "無效選項: $choice"
      echo "可用選項: 0, 1, 2, 3, 4"
      exit 1
      ;;
  esac
}

main() {
  if [[ $# -gt 0 ]]; then
    run_choice "$1"
    exit 0
  fi

  while true; do
    print_menu
    read -r -p "請輸入選項 [0-4]: " choice

    if [[ "$choice" == "0" ]]; then
      run_choice "$choice"
      exit 0
    fi

    run_choice "$choice"
    echo
    read -r -p "按 Enter 返回選單..." _
    echo
  done
}

main "$@"
