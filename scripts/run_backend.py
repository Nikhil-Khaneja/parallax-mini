#!/usr/bin/env python
"""Backend entrypoint: start the MQTT ingest subscriber in a thread, then the API."""
import sys
import threading

sys.path.insert(0, ".")
from backend.db import SessionLocal, init_db  # noqa: E402
from backend.ingest import run_subscriber  # noqa: E402


def main() -> None:
    import uvicorn

    init_db()
    threading.Thread(target=run_subscriber, args=(SessionLocal,), daemon=True).start()
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
