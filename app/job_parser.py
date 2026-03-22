import uuid
from typing import Any, Dict, Optional


def parse_job_from_webhook(
    event_name: str,
    action: str,
    delivery_id: str,
    payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    repo_info = payload.get("repository") or {}
    repo_name = repo_info.get("full_name")
    if not repo_name:
        return None

    if event_name == "issues" and action in {"opened", "labeled"}:
        issue = payload.get("issue") or {}
        issue_number = issue.get("number")
        if issue_number is None:
            return None

        mode = "component"
        if action == "labeled":
            label = (payload.get("label") or {}).get("name", "")
            if label in {"style", "review", "component"}:
                mode = label

        return {
            "id": str(uuid.uuid4()),
            "event_id": delivery_id,
            "repo": repo_name,
            "issue_number": int(issue_number),
            "pr_number": None,
            "task_type": f"issues_{action}",
            "mode": mode,
            "payload": payload,
        }

    if event_name == "pull_request" and action == "opened":
        pr = payload.get("pull_request") or {}
        pr_number = pr.get("number")
        if pr_number is None:
            return None
        return {
            "id": str(uuid.uuid4()),
            "event_id": delivery_id,
            "repo": repo_name,
            "issue_number": None,
            "pr_number": int(pr_number),
            "task_type": "pull_request_opened",
            "mode": "review",
            "payload": payload,
        }

    return None
