#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import json
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def build_payload(repo: str, number: int) -> dict:
    owner, name = repo.split("/", 1)
    return {
        "action": "opened",
        "repository": {
            "id": 1,
            "name": name,
            "full_name": repo,
            "owner": {"login": owner},
        },
        "issue": {"number": number, "title": "MVP dry-run check"},
    }


def send_webhook(url: str, secret: str, payload: dict) -> str:
    body = json.dumps(payload).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    signature = f"sha256={digest}"
    delivery = f"e2e-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-GitHub-Event", "issues")
    req.add_header("X-GitHub-Delivery", delivery)
    req.add_header("X-Hub-Signature-256", signature)

    with urllib.request.urlopen(req, timeout=20) as resp:
        text = resp.read().decode("utf-8")
        data = json.loads(text)
        if data.get("status") != "queued":
            raise RuntimeError(f"unexpected webhook response: {text}")
        job_id = data.get("job_id")
        if not job_id:
            raise RuntimeError(f"missing job_id in webhook response: {text}")
        return str(job_id)


def wait_for_job(db_path: Path, job_id: str, timeout_seconds: int) -> tuple[str, dict]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT status, result_json FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()

        if row is None:
            time.sleep(1)
            continue

        status = row[0]
        result_json = row[1] or "{}"
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            result = {"raw": result_json}

        if status in {"done", "failed"}:
            return status, result
        time.sleep(1)

    raise TimeoutError("timed out waiting job to reach done/failed")


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command dry-run E2E check")
    parser.add_argument("--url", default="http://localhost:8080/webhook")
    parser.add_argument("--secret", required=True)
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--number", type=int, default=999)
    parser.add_argument("--db", default="data/queue.db", help="path to queue.db")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(f"db not found: {db_path}")

    payload = build_payload(args.repo, args.number)
    job_id = send_webhook(args.url, args.secret, payload)
    status, result = wait_for_job(db_path, job_id, args.timeout)

    print(json.dumps({"job_id": job_id, "status": status, "result": result}, ensure_ascii=False))
    if status != "done":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
