from typing import Any, Dict, Optional

import requests

import base64

from config import GITHUB_HOST, GITHUB_TOKEN, GITHUB_USER


class GitHubClient:
    def __init__(self) -> None:
        host = GITHUB_HOST.strip() or "github.com"
        self.base_url = f"https://{host}/api/v3" if host != "github.com" else "https://api.github.com"
        token = GITHUB_TOKEN.strip()
        user = GITHUB_USER.strip()
        if user and token:
            credential = base64.b64encode(f"{user}:{token}".encode()).decode()
            auth_header = f"Basic {credential}"
        elif token:
            auth_header = f"Bearer {token}"
        else:
            auth_header = ""
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if auth_header:
            self.headers["Authorization"] = auth_header

    def create_issue_comment(self, repo: str, issue_number: int, body: str) -> Dict[str, Any]:
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments"
        resp = requests.post(url, headers=self.headers, json={"body": body}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def create_pull_request(
        self,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/repos/{repo}/pulls"
        resp = requests.post(
            url,
            headers=self.headers,
            json={"title": title, "head": head, "base": base, "body": body},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
