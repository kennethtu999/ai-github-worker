#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import json
import urllib.request
from datetime import datetime, timezone


def build_payload(event: str, action: str, repo: str, number: int) -> dict:
    owner, name = repo.split("/", 1)
    base = {
        "action": action,
        "repository": {
            "id": 1,
            "name": name,
            "full_name": repo,
            "owner": {"login": owner},
        },
    }

    if event == "issues":
        base["issue"] = {"number": number, "title": "MVP test issue"}
        if action == "labeled":
            base["label"] = {"name": "component"}
    elif event == "pull_request":
        base["pull_request"] = {"number": number, "title": "MVP test PR"}
    else:
        raise ValueError("event must be issues or pull_request")

    return base


def main() -> None:
    parser = argparse.ArgumentParser(description="Send signed GitHub-like webhook to local MVP")
    parser.add_argument("--url", default="http://localhost:8080/webhook")
    parser.add_argument("--secret", required=True)
    parser.add_argument("--event", choices=["issues", "pull_request"], default="issues")
    parser.add_argument("--action", default="opened")
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--number", type=int, default=1, help="issue/pr number")
    args = parser.parse_args()

    payload = build_payload(args.event, args.action, args.repo, args.number)
    body = json.dumps(payload).encode("utf-8")
    digest = hmac.new(args.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    signature = f"sha256={digest}"
    delivery = f"local-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    req = urllib.request.Request(args.url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-GitHub-Event", args.event)
    req.add_header("X-GitHub-Delivery", delivery)
    req.add_header("X-Hub-Signature-256", signature)

    with urllib.request.urlopen(req, timeout=15) as resp:
        print(resp.status)
        print(resp.read().decode("utf-8"))


if __name__ == "__main__":
    main()
