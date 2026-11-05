"""Health endpoint.

The response model is also the contract-generation smoke test:
change a field here, re-run tools/gen_types, and the generated TS must change.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    ok: bool = Field(description="Service liveness flag")
    service: str = Field(description="Service identifier")
    version: str = Field(description="API version")


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse(ok=True, service="xiuxian-idle", version="0.1.0")
