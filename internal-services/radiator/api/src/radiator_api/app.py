"""HTTP routes. The ingress sends /api here and everything else to radiator-web."""

from datetime import UTC, datetime

from fastapi import FastAPI

from .data import Radiator, radiator

app = FastAPI(title="radiator-api", version="0.0.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/radiator")
def get_radiator() -> Radiator:
    return radiator(datetime.now(UTC))
