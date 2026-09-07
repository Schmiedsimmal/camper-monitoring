"""Minimal-Stub für einen neuen Camper-Monitoring-Service.

Beim Anlegen eines neuen Services diese Datei als Startpunkt nehmen und
die eigentliche Logik in eigene Module unter app/ auslagern.
"""
from __future__ import annotations

import os

from fastapi import FastAPI

app = FastAPI(title="<mein-service>")


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/")
async def index() -> dict:
    return {"service": "<mein-service>", "version": "0.1.0"}


def main() -> None:
    import uvicorn

    port = int(os.environ.get("MEIN_SERVICE_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
