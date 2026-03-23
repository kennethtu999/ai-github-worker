import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from codex_runner import run_codex
from config import CODEX_LOGS_DIR, DEFAULT_BASE_BRANCH, GITHUB_TOKEN, PROMPTS_DIR, WORKER_DRY_RUN
from db import get_job, update_job_status
from github_client import GitHubClient
from workspace import cleanup_workspace, create_workspace, remove_lock


class StepError(Exception):
    def __init__(self, step: str, detail: str):
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail


def _log_job(job_id: str, stage: str, **fields) -> None:
    record = {"component": "worker", "job_id": job_id, "stage": stage, **fields}
    print(json.dumps(record, ensure_ascii=False), flush=True)


def _run_cmd(step: str, cmd: list[str], cwd: Path, job_id: str) -> None:
    _log_job(job_id, "step_started", step=step, command=cmd, cwd=str(cwd))
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as exc:
        _log_job(
            job_id,
            "step_failed",
            step=step,
            command=cmd,
            cwd=str(cwd),
            error=str(exc),
        )
        raise StepError(step, str(exc)) from exc
    _log_job(job_id, "step_succeeded", step=step, command=cmd, cwd=str(cwd))


def _github_git_env() -> Dict[str, str]:
    token = GITHUB_TOKEN.strip()
    if not token:
        raise StepError("github_auth", "GITHUB_TOKEN is empty")
    return {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: Bearer {token}",
    }


def _run_git_with_token(step: str, cmd: list[str], cwd: Path, job_id: str) -> None:
    _log_job(job_id, "step_started", step=step, command=cmd, cwd=str(cwd), auth="github_token")
    env = {**os.environ, **_github_git_env()}
    try:
        subprocess.run(cmd, cwd=cwd, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        _log_job(
            job_id,
            "step_failed",
            step=step,
            command=cmd,
            cwd=str(cwd),
            auth="github_token",
            error=str(exc),
        )
        raise StepError(step, str(exc)) from exc
    _log_job(job_id, "step_succeeded", step=step, command=cmd, cwd=str(cwd), auth="github_token")


def _codex_log_path(job_id: str) -> Path:
    CODEX_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return CODEX_LOGS_DIR / f"{job_id}-{timestamp}.log"


def _prepare_prompt(job: Dict, workspace: Path) -> Path:
    mode = (job.get("mode") or "component").strip().lower()
    if mode not in {"component", "style", "review"}:
        mode = "component"
    prompt_template = PROMPTS_DIR / f"{mode}.txt"
    payload = job.get("payload", {})
    final_prompt = workspace / "prompt.txt"
    text = (
        prompt_template.read_text(encoding="utf-8")
        + "\n\n"
        + _build_job_instruction(job, payload)
        + "\n\nWebhook payload:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    final_prompt.write_text(text, encoding="utf-8")
    return final_prompt


def _build_job_instruction(job: Dict, payload: Dict) -> str:
    if job.get("issue_number"):
        issue = payload.get("issue") or {}
        title = issue.get("title", "")
        body = issue.get("body", "")
        labels = ", ".join(label.get("name", "") for label in issue.get("labels", []) if label.get("name"))
        return (
            "Task source: GitHub issue\n"
            f"Repository: {job['repo']}\n"
            f"Issue number: {job['issue_number']}\n"
            f"Issue title: {title}\n"
            f"Issue labels: {labels or 'none'}\n"
            "Issue body:\n"
            f"{body}\n\n"
            "Execution rules:\n"
            "- Work autonomously with no human intervention.\n"
            "- Implement the issue request end-to-end in code.\n"
            "- Run the required local validation commands and fix failures caused by your changes.\n"
            "- Keep changes minimal and production-ready.\n"
            "- Stop only when the branch is ready to be pushed and opened as a pull request."
        )

    pr = payload.get("pull_request") or {}
    return (
        "Task source: GitHub pull request\n"
        f"Repository: {job['repo']}\n"
        f"PR number: {job.get('pr_number')}\n"
        f"PR title: {pr.get('title', '')}\n"
        "PR body:\n"
        f"{pr.get('body', '')}\n\n"
        "Execution rules:\n"
        "- Work autonomously with no human intervention.\n"
        "- Review the pull request content and make only the necessary code changes.\n"
        "- Run the required local validation commands and fix failures caused by your changes.\n"
        "- Keep the branch in a merge-ready state."
    )


def _simulate_repo_changes(repo_dir: Path, job_id: str) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    marker = repo_dir / "DRY_RUN_RESULT.md"
    marker.write_text(
        "# Dry Run Result\n\n"
        f"job_id: {job_id}\n"
        f"generated_at: {datetime.now(timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )


def _comment_success(github: GitHubClient, job: Dict, branch: str) -> None:
    if job.get("issue_number"):
        body = (
            "✅ Job completed\n"
            f"Branch: {branch}\n"
            "Checks: lint/test/storybook passed"
        )
        github.create_issue_comment(job["repo"], int(job["issue_number"]), body)
    if job.get("pr_number"):
        body = (
            "✅ Review completed\n"
            f"Branch: {branch}\n"
            "Codex review applied"
        )
        github.create_issue_comment(job["repo"], int(job["pr_number"]), body)


def _build_pr_title(job: Dict) -> str:
    payload = job.get("payload", {})
    issue = payload.get("issue") or {}
    issue_title = issue.get("title", "").strip()
    if issue_title:
        return f"AI: {issue_title}"
    return f"AI update for issue #{job['issue_number']}"


def _build_pr_body(job: Dict, branch: str) -> str:
    payload = job.get("payload", {})
    issue = payload.get("issue") or {}
    issue_number = job.get("issue_number")
    lines = [
        "Automated changes generated by ai-github-worker.",
        f"Source branch: `{branch}`",
    ]
    if issue_number:
        lines.append(f"Closes #{issue_number}")
    if issue.get("title"):
        lines.append("")
        lines.append(f"Issue: {issue['title']}")
    return "\n".join(lines)


def _comment_failure(github: GitHubClient, job: Dict, step: str, error: str) -> None:
    body = f"❌ Job failed\nStep: {step}\nError: {error[:500]}"
    if job.get("issue_number"):
        github.create_issue_comment(job["repo"], int(job["issue_number"]), body)
    if job.get("pr_number"):
        github.create_issue_comment(job["repo"], int(job["pr_number"]), body)


def process_job(job_id: str) -> Tuple[str, Dict]:
    job = get_job(job_id)
    if not job:
        _log_job(job_id, "job_missing")
        return "failed", {"step": "load_job", "error": "job not found"}

    repo = job["repo"]
    is_issue_job = bool(job.get("issue_number"))
    if is_issue_job:
        branch = f"feature/{job['issue_number']}"
    elif job.get("pr_number"):
        pr_payload = (job.get("payload") or {}).get("pull_request") or {}
        branch = pr_payload.get("head", {}).get("ref") or f"ai/{job_id}"
    else:
        branch = f"ai/{job_id}"
    clone_url = f"https://github.com/{repo}.git"
    model = (job.get("model") or "").strip() or None
    workspace = create_workspace(job_id)
    repo_dir = workspace / "repo"
    github = GitHubClient()
    codex_log_file: Optional[Path] = None

    try:
        _log_job(
            job_id,
            "job_started",
            repo=repo,
            issue_number=job.get("issue_number"),
            pr_number=job.get("pr_number"),
            mode=job.get("mode"),
            model=model,
            dry_run=WORKER_DRY_RUN,
        )
        if WORKER_DRY_RUN:
            _log_job(job_id, "dry_run_prepare_prompt")
            _prepare_prompt(job, workspace)
            _log_job(job_id, "dry_run_simulate_repo_changes", repo_dir=str(repo_dir))
            _simulate_repo_changes(repo_dir, job_id)
            _log_job(job_id, "job_succeeded", branch=branch, dry_run=True)
            return "done", {
                "branch": branch,
                "checks": "dry-run simulated",
                "dry_run": True,
            }

        _run_git_with_token("clone", ["git", "clone", clone_url, str(repo_dir)], workspace, job_id)
        if is_issue_job:
            _run_cmd("checkout_base", ["git", "checkout", DEFAULT_BASE_BRANCH], repo_dir, job_id)
            _run_git_with_token("pull_base", ["git", "pull", "origin", DEFAULT_BASE_BRANCH], repo_dir, job_id)
            _run_cmd("checkout_branch", ["git", "checkout", "-b", branch], repo_dir, job_id)
        else:
            _run_cmd("checkout_branch", ["git", "checkout", branch], repo_dir, job_id)
            _run_git_with_token("pull_branch", ["git", "pull", "origin", branch], repo_dir, job_id)

        prompt_file = _prepare_prompt(job, workspace)
        codex_log_file = _codex_log_path(job_id)
        _log_job(job_id, "codex_started", prompt_file=str(prompt_file), codex_log=str(codex_log_file))
        try:
            run_codex(prompt_file, repo_dir, codex_log_file, model=model)
        except Exception as exc:
            _log_job(job_id, "codex_failed", error=str(exc), codex_log=str(codex_log_file))
            raise StepError("codex", str(exc)) from exc
        _log_job(job_id, "codex_succeeded", codex_log=str(codex_log_file))

        pr_url = None
        if is_issue_job:
            _run_cmd("npm_ci", ["npm", "ci"], repo_dir, job_id)
            _run_cmd("lint", ["npm", "run", "lint"], repo_dir, job_id)
            _run_cmd("test", ["npm", "test", "--", "--watch=false"], repo_dir, job_id)
            _run_cmd("storybook", ["npm", "run", "build-storybook"], repo_dir, job_id)

            _run_cmd("git_add", ["git", "add", "-A"], repo_dir, job_id)
            commit_msg = f"feat(ai): resolve issue #{job['issue_number']}"
            _log_job(job_id, "step_started", step="git_diff_check", cwd=str(repo_dir))
            diff_check = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=repo_dir,
                check=False,
            )
            if diff_check.returncode == 0:
                _log_job(job_id, "step_failed", step="git_diff_check", cwd=str(repo_dir), error="no code changes produced for pull request")
                raise StepError("git_commit", "no code changes produced for pull request")
            _log_job(job_id, "step_succeeded", step="git_diff_check", cwd=str(repo_dir))
            _run_cmd("git_commit", ["git", "commit", "-m", commit_msg], repo_dir, job_id)
            _run_git_with_token("git_push", ["git", "push", "-u", "origin", branch], repo_dir, job_id)

            _log_job(job_id, "pr_create_started", branch=branch)
            pr_response = github.create_pull_request(
                repo=repo,
                title=_build_pr_title(job),
                head=branch,
                base=DEFAULT_BASE_BRANCH,
                body=_build_pr_body(job, branch),
            )
            pr_url = pr_response.get("html_url")
            _log_job(job_id, "pr_create_succeeded", pr_url=pr_url)

        _comment_success(github, job, branch)
        _log_job(job_id, "comment_success_posted", branch=branch)

        result: Dict = {"branch": branch}
        if is_issue_job:
            result["checks"] = "lint/test/storybook passed"
        if model:
            result["model"] = model
        if codex_log_file is not None:
            result["codex_log"] = str(codex_log_file)
        if pr_url:
            result["pr_url"] = pr_url
        _log_job(job_id, "job_succeeded", **result)
        return "done", result
    except StepError as exc:
        try:
            _comment_failure(github, job, exc.step, exc.detail)
            _log_job(job_id, "comment_failure_posted", step=exc.step)
        except Exception as comment_exc:
            _log_job(job_id, "comment_failure_post_error", step=exc.step, error=str(comment_exc))
        result = {"step": exc.step, "error": exc.detail}
        if codex_log_file is not None:
            result["codex_log"] = str(codex_log_file)
        _log_job(job_id, "job_failed", **result)
        return "failed", result
    except Exception as exc:
        try:
            _comment_failure(github, job, "unexpected", str(exc))
            _log_job(job_id, "comment_failure_posted", step="unexpected")
        except Exception as comment_exc:
            _log_job(job_id, "comment_failure_post_error", step="unexpected", error=str(comment_exc))
        result = {"step": "unexpected", "error": str(exc)}
        if codex_log_file is not None:
            result["codex_log"] = str(codex_log_file)
        _log_job(job_id, "job_failed", **result)
        return "failed", result
    finally:
        _log_job(job_id, "cleanup_started", workspace=str(workspace))
        cleanup_workspace(workspace)
        _log_job(job_id, "cleanup_finished", workspace=str(workspace))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()

    status = "failed"
    result: Dict = {}
    try:
        _log_job(args.job_id, "worker_entry")
        status, result = process_job(args.job_id)
        update_job_status(args.job_id, status, result)
        _log_job(args.job_id, "job_status_updated", status=status, result=result)
    finally:
        remove_lock()
        _log_job(args.job_id, "lock_removed")


if __name__ == "__main__":
    main()
