"""打开存档时惰性补算，进行中的出征只恢复、不自动推进。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.models.api import SettleResponse
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves", tags=["settle"])


class IdleSettleRequest(BaseModel):
    revision: int | None = Field(default=None, ge=1)


@router.post("/{slot_id}/settle", response_model=SettleResponse)
async def settle_slot(
    slot_id: int, payload: IdleSettleRequest | None = None,
    repo: SaveRepository = Depends(get_repo),
) -> SettleResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision if payload else None)
    await commit_mutation(slot_id, command, repo)
    report = command.report
    return SettleResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        elapsed_hours=round(report.elapsed_hours, 4),
        dropped_hours=round(report.dropped_hours, 4),
        gained={
            "cultivation": round(report.cultivation, 2),
            "spirit_stone": round(report.spirit_stone, 2),
            "stamina": round(report.stamina, 2), "materials": report.materials,
        },
        warnings=report.warnings,
    )
