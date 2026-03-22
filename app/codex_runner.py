import os
import subprocess
from pathlib import Path


def run_codex(prompt_file: Path, repo_dir: Path) -> None:
    env = os.environ.copy()
    if not env.get("CODEX_API_KEY") and env.get("OPENAI_API_KEY"):
        env["CODEX_API_KEY"] = env["OPENAI_API_KEY"]

    prompt = prompt_file.read_text(encoding="utf-8")
    cmd = [
        "codex",
        "exec",
        "--ask-for-approval",
        "never",
        "--sandbox",
        "workspace-write",
        "-",
    ]
    subprocess.run(cmd, cwd=repo_dir, env=env, input=prompt, text=True, check=True)
