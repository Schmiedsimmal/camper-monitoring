"""Minimal stub for a new camper-monitoring service.

When creating a new service, use this file as a starting point and
move the actual logic into separate modules under ``app/``.
"""
from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

from shared.web import add_health_route

app = FastAPI(title="<my-service>")


@app.get("/")
async def index() -> dict:
    return {"service": "<my-service>", "version": "0.1.0"}


add_health_route(app)


def main() -> None:
    port = int(os.environ.get("MY_SERVICE_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
