"""丹药定向使用：次数上限、个人加成、疗伤与破境门槛。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.items import use_pill
from app.models.save import ActiveRun, DiscipleState, GameState, Resources

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)

RECIPES = {
    "ju_qi_dan": {
        "id": "ju_qi_dan", "name": "聚气丹", "kind": "pill",
        "inputs": {"ling_cao": 1}, "max_uses": 3,
        "effects": [{"stat": "atk", "mode": "add_pct", "value": .05, "scope": "permanent"}],
    },
    "gu_ti_dan": {
        "id": "gu_ti_dan", "name": "固元丹", "kind": "pill",
        "inputs": {"han_tie": 1}, "max_uses": 3,
        "effects": [{"stat": "def", "mode": "add_pct", "value": .05, "scope": "permanent"}],
    },
    "hui_ling_dan": {
        "id": "hui_ling_dan", "name": "回灵丹", "kind": "pill",
        "inputs": {"ling_cao": 1}, "max_uses": 1,
        "effects": [{"stat": "cultivation_rate", "mode": "add_pct", "value": .1, "scope": "permanent"}],
    },
    "liao_shang_dan": {
        "id": "liao_shang_dan", "name": "疗伤丹", "kind": "pill",
        "inputs": {"ling_cao": 1}, "effects": [], "special": "heal",
    },
    "po_jing_dan": {
        "id": "po_jing_dan", "name": "破境丹", "kind": "pill",
        "inputs": {"xuan_jing": 1}, "effects": [], "special": "realm",
    },
}
TEMPLATES = {
    "t": {
        "id": "t", "name": "测试弟子", "lean": "attack", "rarity": 2,
        "unlock_cost": {"reputation": 100},
        "base_stats": {"hp": 10, "atk": 3, "def": 2, "spd": 4},
    },
}


def make_state(level: int = 1, **inventory: int) -> GameState:
    """构造带两名弟子的存档，便于验证个人效果不会串到别人身上。"""
    return GameState(
        resources=Resources(reputation=500),
        inventory=dict(inventory),
        disciples=[
            DiscipleState(id="d1", template_id="t", level=level),
            DiscipleState(id="d2", template_id="t", level=level),
        ],
    )


def test_attribute_pill_only_buffs_target_and_caps_at_three() -> None:
    """属性丹每次 +5%，每人最多 3 次，不影响其他弟子。"""
    state = make_state(ju_qi_dan=4)

    for _ in range(3):
        assert use_pill(state, "d1", "ju_qi_dan", RECIPES, TEMPLATES) is None
    assert state.disciples[0].bonuses["atk"] == pytest.approx(.15)
    assert state.disciples[1].bonuses == {}
    assert state.bonuses == {}

    assert "最多服用 3 次" in (use_pill(state, "d1", "ju_qi_dan", RECIPES, TEMPLATES) or "")
    assert state.inventory["ju_qi_dan"] == 1


def test_production_pill_is_personal_and_limited_to_one() -> None:
    """回灵丹只写个人值守加成，不写宗门 bonuses，且每人 1 次。"""
    state = make_state(hui_ling_dan=2)

    assert use_pill(state, "d1", "hui_ling_dan", RECIPES, TEMPLATES) is None
    assert state.disciples[0].bonuses["cultivation_rate"] == pytest.approx(.1)
    assert state.bonuses == {}
    assert "最多服用 1 次" in (use_pill(state, "d1", "hui_ling_dan", RECIPES, TEMPLATES) or "")
    assert use_pill(state, "d2", "hui_ling_dan", RECIPES, TEMPLATES) is None


def test_heal_pill_requires_injury_and_clears_all_stacks() -> None:
    """无伤时拒绝且不扣物品；有伤时清空全部伤势。"""
    state = make_state(liao_shang_dan=2)

    assert "没有伤势" in (use_pill(state, "d1", "liao_shang_dan", RECIPES, TEMPLATES) or "")
    assert state.inventory["liao_shang_dan"] == 2

    state.disciples[0].injury_stacks = 2
    state.disciples[0].injured_until = NOW + timedelta(hours=8)
    assert use_pill(state, "d1", "liao_shang_dan", RECIPES, TEMPLATES) is None
    assert state.disciples[0].injury_stacks == 0
    assert state.disciples[0].injured_until is None
    assert state.inventory["liao_shang_dan"] == 1


def test_legacy_healing_pill_is_consumed_before_new_item() -> None:
    """旧 healing_pill 作为别名优先消耗，不自动兑换。"""
    state = make_state(healing_pill=1, liao_shang_dan=1)
    state.disciples[0].injury_stacks = 1

    assert use_pill(state, "d1", "liao_shang_dan", RECIPES, TEMPLATES) is None
    assert "healing_pill" not in state.inventory
    assert state.inventory["liao_shang_dan"] == 1


def test_realm_pill_respects_level_gate_without_spending() -> None:
    """未达到等级门槛时破境丹不扣物品、不提升境界。"""
    state = make_state(level=1, po_jing_dan=1)

    error = use_pill(state, "d1", "po_jing_dan", RECIPES, TEMPLATES)

    assert "需要达到 3 级" in (error or "")
    assert state.disciples[0].realm == 1
    assert state.inventory["po_jing_dan"] == 1


def test_realm_pill_raises_realm_at_level_gate() -> None:
    """达到 3 级后破境丹让指定弟子境界 +1。"""
    state = make_state(level=3, po_jing_dan=1)

    assert use_pill(state, "d1", "po_jing_dan", RECIPES, TEMPLATES) is None
    assert state.disciples[0].realm == 2
    assert state.disciples[1].realm == 1
    assert "po_jing_dan" not in state.inventory


def test_use_rejects_unknown_target_missing_stock_and_active_run() -> None:
    """目标、库存与出征锁定都在扣物品前校验。"""
    state = make_state(ju_qi_dan=1)

    assert use_pill(state, "ghost", "ju_qi_dan", RECIPES, TEMPLATES) == "弟子不存在"
    assert use_pill(state, "d1", "gu_ti_dan", RECIPES, TEMPLATES) == "固元丹不足"

    state.active_run = ActiveRun(run_seed=1, started_at=NOW)
    assert "请先完成当前出征" in (
        use_pill(state, "d1", "ju_qi_dan", RECIPES, TEMPLATES) or ""
    )
    assert state.inventory["ju_qi_dan"] == 1
    assert state.disciples[0].bonuses == {}


def test_use_rejects_disciple_on_run_even_without_busy_flag() -> None:
    """active_run 队伍成员同样不可服药，兼容旧档 busy 丢失。"""
    state = make_state(ju_qi_dan=1)
    state.active_run = ActiveRun(run_seed=1, party=["d1"], started_at=NOW)

    assert "请先完成当前出征" in (
        use_pill(state, "d1", "ju_qi_dan", RECIPES, TEMPLATES) or ""
    )
    assert state.inventory["ju_qi_dan"] == 1

    busy = make_state(ju_qi_dan=1)
    busy.disciples[0].busy = True
    assert "出征中的弟子" in (
        use_pill(busy, "d1", "ju_qi_dan", RECIPES, TEMPLATES) or ""
    )


def test_non_pill_and_unknown_special_are_rejected() -> None:
    """法器与未实现效果不能走服用入口。"""
    assert use_pill(make_state(), "d1", "ghost", RECIPES, TEMPLATES) == "该物品不是可服用的丹药"
    recipes = {**RECIPES, "odd": {
        "id": "odd", "name": "怪丹", "kind": "pill",
        "inputs": {}, "effects": [], "special": "teleport",
    }}
    state = make_state(odd=1)
    assert use_pill(state, "d1", "odd", recipes, TEMPLATES) == "该丹药效果未实现"
    assert state.inventory["odd"] == 1
