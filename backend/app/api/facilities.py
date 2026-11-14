"""设施预览与升级入口，沿用整档 CAS 和旧区间补算。"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.saves import get_repo
from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_facilities
from app.domain.facilities import facility_views, upgrade_facility
from app.models.api import FacilityCommandResponse, FacilityListResponse, RevisionRequest
from app.repositories.saves import SaveRepository

router = APIRouter(prefix="/saves/{slot_id}/facilities", tags=["facilities"])


class UpgradeFacilityRequest(RevisionRequest):
    facility_id: str


@router.get("", response_model=FacilityListResponse)
async def list_facilities(slot_id: int, repo: SaveRepository = Depends(get_repo)) -> FacilityListResponse:
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, revision = loaded
    return FacilityListResponse(revision=revision, facilities=facility_views(state, load_facilities()))


@router.post("/upgrade", response_model=FacilityCommandResponse)
async def upgrade(slot_id: int, payload: UpgradeFacilityRequest, repo: SaveRepository = Depends(get_repo)) -> FacilityCommandResponse:
    command = await prepare_mutation(slot_id, repo, payload.revision)
    error = upgrade_facility(command.state, payload.facility_id, load_facilities())
    if error:
        raise HTTPException(status_code=400, detail=error)
    await commit_mutation(slot_id, command, repo)
    return FacilityCommandResponse(
        **snapshot(command.state, command.revision + 1).model_dump(),
        facilities=facility_views(command.state, load_facilities()),
    )
