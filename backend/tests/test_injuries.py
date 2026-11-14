"""伤势测试：叠加、战斗修正、失败挂伤与保底收益。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.injuries import (
    HOURS_PER_STACK,
    MAX_INJURY_STACKS,
    apply_injury,
    attack_multiplier,
    heal,
)
from app.domain.run_engine import (
    choose,
    party_power,
    settle_run,
    start_run,
)
from app.domain.settle import settle
from app.models.save import DiscipleState, GameState, Resources, RunNode

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)

MODE = {
    "id": "tower",
    "stamina_cost": 1,
    "node_count": 20,
    "start_hp": 300,
    "base_enemy_power": 20,
    "enemy_growth": 0.4,
    "reward_growth": 0.1,
    "damage_scale": 60,
    "boss_every": 5,
    "choices_per_step": 2,
    "elite_chance": 20,
    "defeat_ratio": 0.5,
    "defeat_floor_reward": {"cultivation": 3.0},
    "rewards": {
        "battle": {"cultivation": 10.0, "spirit_stone": 5.0},
        "elite": {"cultivation": 20.0, "spirit_stone": 10.0},
        "boss": {"cultivation": 50.0, "spirit_stone": 25.0},
    },
    "encounters": {"battle": ["test_enemy"], "elite": ["test_enemy"], "boss": ["test_boss"]},
}

BONDS: dict[str, dict] = {}

TEMPLATES = {
    "d_strong": {
        "id": "d_strong",
        "lean": "attack",
        "rarity": 3,
        "base_stats": {"hp": 100, "atk": 20, "def": 10, "spd": 10},
    },
    "d_weak": {
        "id": "d_weak",
        "lean": "support",
        "rarity": 1,
        "base_stats": {"hp": 20, "atk": 1, "def": 1, "spd": 1},
    },
}


def make_state(template_id: str = "d_strong") -> GameState:
    """构造带一名弟子的存档。"""
    return GameState(
        resources=Resources(stamina=3.0),
        disciples=[DiscipleState(id="d1", template_id=template_id)],
    )


_start_run = start_run


def start_run(*args, **kwargs):
    enemies = {
        "test_enemy": {"id": "test_enemy", "name": "测试灵卫", "base_stats": {"hp": 35, "atk": 4, "def": 2, "spd": 8}},
        "test_boss": {"id": "test_boss", "name": "测试首领", "base_stats": {"hp": 5, "atk": 1, "def": 1, "spd": 8}},
    }
    return _start_run(*args, enemies=enemies, affix_pool=[], skills={}, **kwargs)


def test_attack_multiplier_is_linear_and_capped() -> None:
    """每层扣 10%，最多扣到 3 层。"""
    assert attack_multiplier(0) == pytest.approx(1.0)
    assert attack_multiplier(1) == pytest.approx(0.9)
    assert attack_multiplier(MAX_INJURY_STACKS) == pytest.approx(0.7)
    assert attack_multiplier(99) == pytest.approx(0.7)


def test_apply_injury_extends_timer_by_stack() -> None:
    """每叠加一层，消退时间按层数顺延。"""
    disciple = DiscipleState(id="d1", template_id="t")

    apply_injury(disciple, NOW)
    assert disciple.injury_stacks == 1
    assert disciple.injured_until == NOW + timedelta(hours=HOURS_PER_STACK)

    apply_injury(disciple, NOW)
    assert disciple.injury_stacks == 2
    assert disciple.injured_until == NOW + timedelta(hours=HOURS_PER_STACK * 2)


def test_injury_caps_at_three_stacks() -> None:
    """连续失败最多叠到 3 层。"""
    disciple = DiscipleState(id="d1", template_id="t")
    for _ in range(5):
        apply_injury(disciple, NOW)

    assert disciple.injury_stacks == MAX_INJURY_STACKS


def test_heal_clears_injury() -> None:
    """疗伤丹立即清空层数与到期时间。"""
    disciple = DiscipleState(
        id="d1",
        template_id="t",
        injury_stacks=2,
        injured_until=NOW + timedelta(hours=8),
    )

    heal(disciple)

    assert disciple.injury_stacks == 0
    assert disciple.injured_until is None


def test_injury_lowers_party_power() -> None:
    """带伤只削攻击，不削防御与气血。"""
    state = make_state()
    state.disciples[0].injury_stacks = 2

    assert party_power(state.disciples, TEMPLATES) == pytest.approx(31.0)


def test_defeat_attaches_injury() -> None:
    """失败结算后队伍获得一层伤势。"""
    state = make_state("d_weak")
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    choose(state, 0, TEMPLATES, [], MODE, BONDS)

    settle_run(state, MODE, NOW)

    assert state.disciples[0].injury_stacks == 1
    assert state.disciples[0].injured_until == NOW + timedelta(hours=HOURS_PER_STACK)


def test_defeat_grants_floor_reward() -> None:
    """首层失败也有保底收益，不会断粮。"""
    state = make_state("d_weak")
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    choose(state, 0, TEMPLATES, [], MODE, BONDS)

    result = settle_run(state, MODE, NOW)

    assert result["loot"]["cultivation"] == pytest.approx(3.0)
    assert state.resources.cultivation == pytest.approx(3.0)
    assert state.last_run_review is not None
    assert state.last_run_review.victory is False
    assert state.last_run_review.cleared == 1
    assert state.last_run_review.last_battle is not None
    assert state.last_run_review.last_battle.won is False


def test_victory_does_not_injure() -> None:
    """通关不挂伤。"""
    state = make_state()
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    state.active_run.nodes = [
        RunNode(kind="battle", enemy=f"battle_{i}", power=1)
        for i in range(MODE["node_count"] - 1)
    ]
    state.active_run.choices = [RunNode(kind="boss", enemy="boss_9", power=1)]

    choose(state, 0, TEMPLATES, [], MODE, BONDS)
    result = settle_run(state, MODE, NOW)

    assert state.disciples[0].injury_stacks == 0
    assert result["victory"] is True
    assert state.last_run_review is not None
    assert state.last_run_review.victory is True
    assert state.last_run_review.cleared == MODE["node_count"]
    assert state.last_run_review.last_battle is not None
    assert state.last_run_review.last_battle.won is True


def test_injury_does_not_affect_idle_output() -> None:
    """伤势只在战斗内生效，挂机产出照旧。"""
    state = make_state()
    state.disciples[0].injury_stacks = 3

    settle(state, NOW, NOW + timedelta(hours=1))

    assert state.resources.cultivation == pytest.approx(1.0)
