import json
import subprocess
import sys
import time
from pathlib import Path

from config import SCHEDULER_INTERVAL_SECONDS, WORKER_LOGS_DIR
from db import claim_next_queued_job
from workspace import create_lock, lock_exists, remove_lock


def _log_scheduler(stage: str, **fields) -> None:
    record = {"component": "scheduler", "stage": stage, **fields}
    print(json.dumps(record, ensure_ascii=False), flush=True)


def _worker_log_path(job_id: str) -> Path:
    WORKER_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return WORKER_LOGS_DIR / f"{job_id}.log"


def run_scheduler_forever() -> None:
    _log_scheduler("started", interval_seconds=SCHEDULER_INTERVAL_SECONDS)
    while True:
        try:
            tick()
        except Exception as exc:
            _log_scheduler("unexpected_error", error=str(exc))
        time.sleep(SCHEDULER_INTERVAL_SECONDS)


def tick() -> None:
    if lock_exists():
        _log_scheduler("skip", reason="lock_exists")
        return

    job = claim_next_queued_job()
    if not job:
        _log_scheduler("idle")
        return

    script_path = Path(__file__).resolve().parent / "run_job.py"
    worker_log_path = _worker_log_path(job["id"])
    with worker_log_path.open("a", encoding="utf-8") as worker_log:
        proc = subprocess.Popen(
            [sys.executable, str(script_path), "--job-id", job["id"]],
            stdout=worker_log,
            stderr=subprocess.STDOUT,
        )

    if proc.pid is None:
        remove_lock()
        raise RuntimeError("worker process has no pid")

    create_lock(job["id"], proc.pid)
    _log_scheduler(
        "job_started",
        job_id=job["id"],
        pid=proc.pid,
        worker_log=str(worker_log_path),
    )
