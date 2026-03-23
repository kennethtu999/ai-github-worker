import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def run_codex(prompt_file: Path, repo_dir: Path, log_file: Path, model: Optional[str] = None) -> None:
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
    ]
    if model:
        cmd.extend(["--model", model])
    cmd.append("-")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w", encoding="utf-8") as handle:
        started_at = datetime.now(timezone.utc).isoformat()
        handle.write(f"repo_dir: {repo_dir}\n")
        handle.write(f"prompt_file: {prompt_file}\n")
        handle.write(f"model: {model or 'default'}\n")
        handle.write(f"command: {' '.join(cmd)}\n\n")
        handle.write(f"started_at: {started_at}\n\n")
        handle.flush()
        result = subprocess.run(
            cmd,
            cwd=repo_dir,
            env=env,
            input=prompt,
            text=True,
            check=False,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
        finished_at = datetime.now(timezone.utc).isoformat()
        handle.write(f"\nfinished_at: {finished_at}\n")
        handle.write(f"exit_code: {result.returncode}\n")
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd)
