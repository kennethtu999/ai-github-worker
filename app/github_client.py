from typing import Any, Dict, Optional

import requests

from config import GITHUB_TOKEN


class GitHubClient:
    def __init__(self) -> None:
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

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
