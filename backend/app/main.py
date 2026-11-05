"""FastAPI application entrypoint.

Kept intentionally thin at T00: only the health endpoint exists.
Domain logic, repositories and database wiring land in T02+.
"""

from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="Xiuxian Idle API",
    version="0.1.0",
    description="Self-hosted idle roguelite. Single player, multi-slot saves.",
)

app.include_router(health_router, prefix="/api")
