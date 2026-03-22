import hashlib
import hmac
import json

from fastapi import FastAPI, Header, HTTPException, Request

from config import GITHUB_WEBHOOK_SECRET
from db import enqueue_job, is_event_processed, mark_event_processed
from job_parser import parse_job_from_webhook


app = FastAPI(title="ai-github-worker")


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
    if not _verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="invalid signature")

    if not x_github_delivery:
        raise HTTPException(status_code=400, detail="missing delivery id")

    if is_event_processed(x_github_delivery):
        return {"status": "duplicate", "event_id": x_github_delivery}

    payload = json.loads(body.decode("utf-8"))
    action = payload.get("action", "")
    job = parse_job_from_webhook(x_github_event, action, x_github_delivery, payload)
    mark_event_processed(x_github_delivery)

    if job is None:
        return {"status": "ignored", "event": x_github_event, "action": action}

    enqueue_job(job)
    return {"status": "queued", "job_id": job["id"]}
