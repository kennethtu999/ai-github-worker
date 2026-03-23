import hashlib
import hmac
import json

from fastapi import FastAPI, Header, HTTPException, Request

from config import GITHUB_WEBHOOK_SECRET
from db import enqueue_job, is_event_processed, mark_event_processed
from job_parser import parse_job_from_webhook


app = FastAPI(title="ai-github-worker")


def _log_webhook(stage: str, **fields) -> None:
    record = {"component": "webhook", "stage": stage, **fields}
    print(json.dumps(record, ensure_ascii=False), flush=True)


def _verify_signature(body: bytes, signature_256: str) -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        return False
    digest = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature_256)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
):
    body = await request.body()
    payload = {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        pass

    action = payload.get("action", "")
    repo = (payload.get("repository") or {}).get("full_name", "")
    _log_webhook(
        "received",
        event=x_github_event,
        action=action,
        delivery_id=x_github_delivery,
        repo=repo,
    )

    if not _verify_signature(body, x_hub_signature_256):
        _log_webhook(
            "rejected",
            reason="invalid_signature",
            event=x_github_event,
            action=action,
            delivery_id=x_github_delivery,
            repo=repo,
        )
        raise HTTPException(status_code=401, detail="invalid signature")

    if not x_github_delivery:
        _log_webhook(
            "rejected",
            reason="missing_delivery_id",
            event=x_github_event,
            action=action,
            repo=repo,
        )
        raise HTTPException(status_code=400, detail="missing delivery id")

    if is_event_processed(x_github_delivery):
        _log_webhook(
            "duplicate",
            event=x_github_event,
            action=action,
            delivery_id=x_github_delivery,
            repo=repo,
        )
        return {"status": "duplicate", "event_id": x_github_delivery}

    ignore_context = {}
    job = parse_job_from_webhook(
        x_github_event,
        action,
        x_github_delivery,
        payload,
        ignore_context=ignore_context,
    )
    mark_event_processed(x_github_delivery)

    if job is None:
        _log_webhook(
            "ignored",
            reason=ignore_context.get("reason", "unknown"),
            event=x_github_event,
            action=action,
            delivery_id=x_github_delivery,
            repo=repo,
            **{k: v for k, v in ignore_context.items() if k != "reason"},
        )
        return {"status": "ignored", "event": x_github_event, "action": action}

    enqueue_job(job)
    _log_webhook(
        "queued",
        event=x_github_event,
        action=action,
        delivery_id=x_github_delivery,
        repo=repo,
        job_id=job["id"],
        task_type=job.get("task_type"),
        mode=job.get("mode"),
    )
    return {"status": "queued", "job_id": job["id"]}
