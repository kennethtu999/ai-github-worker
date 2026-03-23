import os
from pathlib import Path


BASE_DIR = Path(os.getenv("APP_BASE_DIR", "/app"))
DATA_DIR = BASE_DIR / "data"
REPOS_DIR = BASE_DIR / "repos"
PROMPTS_DIR = BASE_DIR / "app" / "prompts"
CODEX_LOGS_DIR = Path(os.getenv("CODEX_LOGS_DIR", str(DATA_DIR / "codex_logs")))

DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "queue.db")))
WORKER_LOCK_PATH = Path(os.getenv("WORKER_LOCK_PATH", str(DATA_DIR / "worker.lock")))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
CODEX_API_KEY = os.getenv("CODEX_API_KEY", os.getenv("OPENAI_API_KEY", ""))

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))

SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "5"))
DEFAULT_BASE_BRANCH = os.getenv("DEFAULT_BASE_BRANCH", "main")


def _env_bool(name: str, default: bool = False) -> bool:
	raw = os.getenv(name)
	if raw is None:
		return default
	return raw.strip().lower() in {"1", "true", "yes", "on"}


WORKER_DRY_RUN = _env_bool("WORKER_DRY_RUN", default=False)
