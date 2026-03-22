import json
import os
import shutil
from pathlib import Path
from typing import Dict

from config import REPOS_DIR, WORKER_LOCK_PATH


def create_workspace(job_id: str) -> Path:
    workspace = REPOS_DIR / job_id
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def cleanup_workspace(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def lock_exists() -> bool:
    if not WORKER_LOCK_PATH.exists():
        return False

    try:
        payload = json.loads(WORKER_LOCK_PATH.read_text(encoding="utf-8") or "{}")
        pid = int(payload.get("pid", 0))
    except Exception:
        remove_lock()
        return False

    if pid <= 0:
        remove_lock()
        return False

    try:
        os.kill(pid, 0)
    except OSError:
        remove_lock()
        return False

    return True


def create_lock(job_id: str, pid: int) -> None:
    WORKER_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, object] = {"job_id": job_id, "pid": pid}
    WORKER_LOCK_PATH.write_text(json.dumps(payload), encoding="utf-8")


def remove_lock() -> None:
    if WORKER_LOCK_PATH.exists():
        WORKER_LOCK_PATH.unlink()
