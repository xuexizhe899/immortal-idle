"""设施等级解锁成长上限；升级消耗在一次命令内扣除。"""

from app.models.api import FacilityView
from app.models.save import GameState

MAX_FACILITY_LEVEL = 3
GRADE_MULTIPLIERS = {1: 1.0, 2: 1.5, 3: 2.0}


def facility_views(state: GameState, definitions: dict[str, dict]) -> list[FacilityView]:
    views = []
    for facility_id, definition in definitions.items():
        level = state.facility_levels.get(facility_id, 1)
        costs = definition["costs"][level - 1] if level < MAX_FACILITY_LEVEL else {}
        reason = ""
        if state.active_run is not None:
            reason = "请先完成当前出征再升级设施"
        elif level >= MAX_FACILITY_LEVEL:
            reason = "已达当前最高等级"
        elif facility_id != "hall" and level >= state.facility_levels.get("hall", 1):
            reason = "请先升级宗门主殿"
        elif any(
            (getattr(state.resources, key) if key in type(state.resources).model_fields else state.inventory.get(key, 0)) < count
            for key, count in costs.items()
        ):
            reason = "升级资源不足"
        views.append(FacilityView(
            id=facility_id, name=definition["name"], level=level,
            description=definition["descriptions"][level - 1],
            next_description=definition["descriptions"][level] if level < MAX_FACILITY_LEVEL else "",
            costs=costs, upgradeable=not reason, reason=reason,
        ))
    return views


def upgrade_facility(state: GameState, facility_id: str, definitions: dict[str, dict]) -> str | None:
    if facility_id not in definitions:
        return "设施不存在"
    view = next(item for item in facility_views(state, definitions) if item.id == facility_id)
    if view.reason:
        return view.reason
    # 先校验全量费用，避免升级失败时扣走部分材料。
    for key, count in view.costs.items():
        if key in type(state.resources).model_fields:
            setattr(state.resources, key, getattr(state.resources, key) - count)
        else:
            remaining = state.inventory.get(key, 0) - int(count)
            if remaining:
                state.inventory[key] = remaining
            else:
                state.inventory.pop(key, None)
    state.facility_levels[facility_id] = view.level + 1
    return None
