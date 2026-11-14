"""存档相关的 Pydantic 模型。

存档整档存为一份 JSON（state_json），这里的模型就是那份 JSON 的结构，
同时通过 OpenAPI 生成前端类型，是前后端唯一契约来源。
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from app.models.base import ContractModel as BaseModel
from app.models.battle import BattleBond, BattleEvent, BattleUnit, BattleUnitState, EnemyDefinition

CURRENT_SCHEMA_VERSION = 1
FacilityLevel = Annotated[int, Field(ge=1, le=3)]


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
    # 个人永久加成（丹药等），加区小数；与宗门 bonuses 分开，出发时再合并。
    bonuses: dict[str, float] = Field(default_factory=dict)
    equipment: list[str] = Field(default_factory=list)
    # 个人丹药使用次数，用于每种丹药的服用上限；旧档默认空。
    pill_uses: dict[str, int] = Field(default_factory=dict)
    # 同类属性丹的强化名额保存品级，高阶丹仅替换低阶差额。
    pill_grades: dict[str, list[FacilityLevel]] = Field(default_factory=dict)
    injury_stacks: int = 0
    injured_until: datetime | None = None
    busy: bool = False


class DutySlot(BaseModel):
    """值守编制中的一个位置。"""

    disciple_id: str
    assigned_at: datetime


class NpcSect(BaseModel):
    """生成后固定的外宗身份、守军与驻守编制。"""

    id: str
    name: str
    level: int = Field(ge=1, le=3)
    style: str
    material_id: str
    special_material_id: str
    arena_teams: list[list[BattleUnit]] = Field(default_factory=list)
    leader: BattleUnit
    loot: dict[str, float] = Field(default_factory=dict)
    conquered: bool = False
    garrison: list[DutySlot] = Field(default_factory=list, max_length=3)


class DutyEvent(BaseModel):
    """值守变更事件，供惰性结算分段使用。"""

    at: datetime
    rates: dict[str, float] = Field(default_factory=dict)


class RunNode(BaseModel):
    """出征路线上的一个节点。"""

    kind: str
    enemy: str
    # 候选的实际编成；为空表示旧局节点，按类型与层数回退生成。
    enemies: list[str] = Field(default_factory=list)
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


class BattleReview(BaseModel):
    """结算后保留的最近一场关键战报，不复制逐行动演出。"""

    node: RunNode
    party_power: float
    enemy_power: int
    hp_before: int
    hp_after: int
    damage: int
    healed: int = 0
    shield_applied: int | None = None
    shield_absorbed: int | None = None
    won: bool
    rounds: int = 0
    reason: str = "victory"
    first_down_id: str | None = None
    first_down_name: str | None = None
    surviving_enemies: list[BattleUnitState] = Field(default_factory=list, max_length=6)
    key_actions: list[dict[str, str | int]] = Field(default_factory=list, max_length=3)


class RunReview(BaseModel):
    """最近一次已结算出征的事实摘要，供下次准备时复盘。"""

    mode: str
    sect_id: str | None = None
    sect_name: str | None = None
    tower_tier: int = 1
    cleared: int
    total_nodes: int
    victory: bool
    end_reason: str | None = None
    loot: dict[str, float] = Field(default_factory=dict)
    last_battle: BattleReview | None = None


class RunPartySnapshot(BaseModel):
    """出发时固化所有战斗和后续节点定义，配置修改不改变本局。"""

    model_config = ConfigDict(frozen=True)

    combatants: tuple[BattleUnit, ...]
    bonds: tuple[BattleBond, ...] = ()
    mode: dict = Field(default_factory=dict)
    affix_pool: list[dict] = Field(default_factory=list)
    enemies: dict[str, EnemyDefinition] = Field(default_factory=dict)
    # 节点结构版本：1 表示旧局（同类型共用编成），2 表示逐候选编成。
    route_version: Literal[1, 2] = 1


class ActiveRun(BaseModel):
    """进行中的一次出征；结束时整体清空。"""

    run_seed: int
    rng_cursor: int = 0
    mode: str = "tower"
    sect_id: str | None = None
    guard: int = Field(default=100, ge=0, le=100)
    arena_round: int = Field(default=0, ge=0, le=3)
    selected_party: list[str] = Field(default_factory=list)
    deployed: list[str] = Field(default_factory=list)
    # 出发前的岗位按弟子保存，结算时只恢复仍有空位的岗位。
    return_posts: dict[str, str] = Field(default_factory=dict)
    tower_tier: int = Field(default=1, ge=1, le=3)
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
    # 已打造的一次性器方；丹药可重复炼制，不写入这里。
    crafted_recipes: list[str] = Field(default_factory=list)
    unlocks: list[str] = Field(default_factory=list)
    tower_floor: int = 0
    expedition_floor: int = 0
    facility_levels: dict[str, FacilityLevel] = Field(default_factory=lambda: {
        "hall": 1, "forge": 1, "alchemy": 1, "tower": 1, "training": 1,
    })
    recipe_levels: dict[str, FacilityLevel] = Field(default_factory=dict)
    weapon_levels: dict[str, FacilityLevel] = Field(default_factory=dict)
    tower_tiers: dict[str, int] = Field(default_factory=dict)
    sects: list[NpcSect] = Field(default_factory=list)
    last_run_review: RunReview | None = None
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
