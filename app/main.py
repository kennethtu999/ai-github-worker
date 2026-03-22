import threading

import uvicorn

from config import WEBHOOK_HOST, WEBHOOK_PORT
from db import init_db
from scheduler import run_scheduler_forever
from webhook_server import app


def main() -> None:
    init_db()
    scheduler_thread = threading.Thread(target=run_scheduler_forever, daemon=True)
    scheduler_thread.start()
    uvicorn.run(app, host=WEBHOOK_HOST, port=WEBHOOK_PORT)


if __name__ == "__main__":
    main()
