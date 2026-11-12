"""存档相关的 Pydantic 模型。

存档整档存为一份 JSON（state_json），这里的模型就是那份 JSON 的结构，
同时通过 OpenAPI 生成前端类型，是前后端唯一契约来源。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict, Field

from app.models.base import ContractModel as BaseModel
from app.models.battle import BattleBond, BattleEvent, BattleUnit, BattleUnitState, EnemyDefinition

CURRENT_SCHEMA_VERSION = 1


class Resources(BaseModel):
    """局外资源存量；用浮点是因为按小时产出会产生小数。"""

    cultivation: float = 0.0
    spirit_stone: float = 0.0
    stamina: float = 0.0
    reputation: float = 0.0


class DiscipleState(BaseModel):
    """一名弟子的运行时状态。"""

    id: str
    template_id: str
    level: int = 1
    exp: int = 0
    realm: int = 1
    stats: dict[str, float] = Field(default_factory=dict)
    equipment: list[str] = Field(default_factory=list)
    injury_stacks: int = 0
    injured_until: datetime | None = None
    busy: bool = False


class DutySlot(BaseModel):
    """值守编制中的一个位置。"""

    disciple_id: str
    assigned_at: datetime


class DutyEvent(BaseModel):
    """值守变更事件，供惰性结算分段使用。"""

    at: datetime
    rates: dict[str, float] = Field(default_factory=dict)


class RunNode(BaseModel):
    """出征路线上的一个节点。"""

    kind: str
    enemy: str
    power: int
    reward: dict[str, float] = Field(default_factory=dict)


class BattleSummary(BaseModel):
    """服务端已结算的一场战斗及逐行动战报。"""

    id: str
    party_power: float
    enemy_power: int
    hp_before: int
    hp_after: int
    damage: int
    healed: int = 0
    won: bool
    loot: dict[str, float] = Field(default_factory=dict)
    node: RunNode
    rounds: int = 0
    reason: str = "victory"
    initial_units: list[BattleUnitState] = Field(default_factory=list)
    final_units: list[BattleUnitState] = Field(default_factory=list)
    events: list[BattleEvent] = Field(default_factory=list)


class RunPartySnapshot(BaseModel):
    """出发时固化所有战斗和后续节点定义，配置修改不改变本局。"""

    model_config = ConfigDict(frozen=True)

    combatants: tuple[BattleUnit, ...]
    bonds: tuple[BattleBond, ...] = ()
    mode: dict = Field(default_factory=dict)
    affix_pool: list[dict] = Field(default_factory=list)
    enemies: dict[str, EnemyDefinition] = Field(default_factory=dict)


class ActiveRun(BaseModel):
    """进行中的一次出征；结束时整体清空。"""

    run_seed: int
    rng_cursor: int = 0
    mode: str = "tower"
    party: list[str] = Field(default_factory=list)
    party_snapshot: RunPartySnapshot | None = None
    hp: int = 0
    max_hp: int = 0
    member_hp: dict[str, int] = Field(default_factory=dict)
    end_reason: str | None = None
    nodes: list[RunNode] = Field(default_factory=list)
    choices: list[RunNode] = Field(default_factory=list)
    affix_options: list[str] = Field(default_factory=list)
    affix_pending: bool = False
    affixes: list[str] = Field(default_factory=list)
    pending_loot: dict[str, float] = Field(default_factory=dict)
    last_battle: BattleSummary | None = None
    started_at: datetime


class GameState(BaseModel):
    """整档游戏状态，对应 save_slots.state_json。"""

    schema_version: int = CURRENT_SCHEMA_VERSION
    resources: Resources = Field(default_factory=Resources)
    disciples: list[DiscipleState] = Field(default_factory=list)
    duty_slots: list[DutySlot] = Field(default_factory=list)
    duty_events: list[DutyEvent] = Field(default_factory=list)
    inventory: dict[str, int] = Field(default_factory=dict)
    material_remainders: dict[str, float] = Field(default_factory=dict)
    bonuses: dict[str, float] = Field(default_factory=dict)
    unlocks: list[str] = Field(default_factory=list)
    tower_floor: int = 0
    active_run: ActiveRun | None = None
    rng_seed: int = 0
    logs: list[str] = Field(default_factory=list)


class SaveSlotMeta(BaseModel):
    """存档槽的元信息，不含 state_json。"""

    slot_id: int
    name: str
    revision: int
    schema_version: int
    last_settled_at: datetime
    updated_at: datetime


class SaveExport(BaseModel):
    """导出/导入存档的载荷，导入时由 Pydantic 在边界校验一次。"""

    name: str = "导入的存档"
    schema_version: int = CURRENT_SCHEMA_VERSION
    state: GameState
