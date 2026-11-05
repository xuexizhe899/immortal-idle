"""存档相关的 Pydantic 模型。

存档整档存为一份 JSON（state_json），这里的模型就是那份 JSON 的结构，
同时通过 OpenAPI 生成前端类型，是前后端唯一契约来源。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

CURRENT_SCHEMA_VERSION = 1


class Resources(BaseModel):
    """局外资源存量；用浮点是因为按小时产出会产生小数。"""

    cultivation: float = 0.0
    spirit_stone: float = 0.0
    stamina: float = 0.0


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
    busy_until: datetime | None = None


class DutySlot(BaseModel):
    """值守编制中的一个位置。"""

    disciple_id: str
    assigned_at: datetime


class DutyEvent(BaseModel):
    """值守变更事件，供惰性结算分段使用。"""

    at: datetime
    rates: dict[str, float] = Field(default_factory=dict)


class ActiveRun(BaseModel):
    """进行中的一次出征；结束时整体清空。"""

    run_seed: int
    rng_cursor: int = 0
    mode: str
    node_index: int = 0
    affixes: list[str] = Field(default_factory=list)
    pending_loot: dict[str, int] = Field(default_factory=dict)
    started_at: datetime


class GameState(BaseModel):
    """整档游戏状态，对应 save_slots.state_json。"""

    schema_version: int = CURRENT_SCHEMA_VERSION
    resources: Resources = Field(default_factory=Resources)
    disciples: list[DiscipleState] = Field(default_factory=list)
    duty_slots: list[DutySlot] = Field(default_factory=list)
    duty_events: list[DutyEvent] = Field(default_factory=list)
    inventory: dict[str, int] = Field(default_factory=dict)
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
