import subprocess
import time
from pathlib import Path

from config import SCHEDULER_INTERVAL_SECONDS
from db import claim_next_queued_job
from workspace import create_lock, lock_exists, remove_lock


def run_scheduler_forever() -> None:
    while True:
        try:
            tick()
        except Exception as exc:
            print(f"[scheduler] unexpected error: {exc}", flush=True)
        time.sleep(SCHEDULER_INTERVAL_SECONDS)


def tick() -> None:
    if lock_exists():
        return

    job = claim_next_queued_job()
    if not job:
        return

    script_path = Path(__file__).resolve().parent / "run_job.py"
    proc = subprocess.Popen(
        ["python", str(script_path), "--job-id", job["id"]],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if proc.pid is None:
        remove_lock()
        raise RuntimeError("worker process has no pid")

    create_lock(job["id"], proc.pid)
    print(f"[scheduler] started job {job['id']} pid={proc.pid}", flush=True)
