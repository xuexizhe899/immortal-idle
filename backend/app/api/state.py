"""共享命令边界：先校验版本、补算，再把状态与结算锚点原子写回。"""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config_loader import load_bonds, load_disciples
from app.domain.duty import rates_of, record_event
from app.domain.run_engine import run_status
from app.domain.settle import (
    BASE_CULTIVATION_PER_HOUR, BASE_MATERIALS_PER_HOUR,
    BASE_SPIRIT_STONE_PER_HOUR, BASE_STAMINA_PER_HOUR, SettleReport, settle,
)
from app.models.api import GameSnapshot, RunStatus
from app.models.save import GameState
from app.repositories.saves import SaveRepository


def status_of(state: GameState) -> RunStatus:
    if state.active_run is None:
        return "idle"
    return run_status(state.active_run)


def snapshot(state: GameState, revision: int) -> GameSnapshot:
    rates = rates_of(state, load_disciples(), load_bonds())
    for key, value in state.bonuses.items():
        rates[key] = rates.get(key, 0.0) + value
    return GameSnapshot(
        state=state, revision=revision, status=status_of(state),
        production={
            "cultivation": BASE_CULTIVATION_PER_HOUR * (1 + rates.get("cultivation_rate", 0)),
            "spirit_stone": BASE_SPIRIT_STONE_PER_HOUR * (1 + rates.get("spirit_stone_rate", 0)),
            "stamina": BASE_STAMINA_PER_HOUR * (1 + rates.get("stamina_rate", 0)),
            "materials": {
                key: base * (1 + rates.get("material_rate", 0))
                for key, base in BASE_MATERIALS_PER_HOUR.items()
            },
            "injury_recovery_multiplier": 1 + rates.get("injury_rate", 0),
        },
    )


@dataclass
class Mutation:
    state: GameState
    revision: int
    now: datetime
    settled_at: datetime
    report: SettleReport


async def prepare_mutation(
    slot_id: int, repo: SaveRepository, revision: int | None,
) -> Mutation:
    loaded = await repo.get_state(slot_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    state, current = loaded
    if revision is not None and revision != current:
        raise HTTPException(status_code=409, detail="存档已更新，请刷新后重试")
    last = await repo.get_last_settled_at(slot_id)
    if last is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    now = datetime.now(timezone.utc)
    report = settle(state, last, now)
    return Mutation(state, current, now, max(last, now), report)


async def commit_mutation(slot_id: int, mutation: Mutation, repo: SaveRepository) -> None:
    current_rates = rates_of(mutation.state, load_disciples(), load_bonds())
    last_rates = mutation.state.duty_events[-1].rates if mutation.state.duty_events else {}
    if current_rates != last_rates:
        record_event(mutation.state, load_disciples(), mutation.settled_at, load_bonds())
    if not await repo.save_state(
        slot_id, mutation.state, mutation.revision, settled_at=mutation.settled_at,
    ):
        raise HTTPException(status_code=409, detail="存档已更新，请刷新后重试")
