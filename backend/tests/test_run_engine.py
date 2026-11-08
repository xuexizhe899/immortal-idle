"""出征引擎测试：状态流转、战斗、结算与重放。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.run_engine import (
    choose,
    party_power,
    pick_affix,
    run_status,
    settle_run,
    start_run,
)
from app.models.save import DiscipleState, GameState, Resources, RunNode

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)

MODE = {
    "id": "tower",
    "name": "问道塔",
    "stamina_cost": 1,
    "node_count": 10,
    "start_hp": 300,
    "base_enemy_power": 30,
    "choices_per_step": 2,
    "elite_chance": 20,
    "defeat_ratio": 0.5,
    "defeat_floor_reward": {"cultivation": 3.0},
    "rewards": {
        "battle": {"cultivation": 10.0, "spirit_stone": 5.0},
        "elite": {"cultivation": 20.0, "spirit_stone": 10.0},
        "boss": {"cultivation": 50.0, "spirit_stone": 25.0},
    },
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

AFFIXES = [
    {"id": "fire_1", "group": "fire", "weight": 1.0},
    {"id": "fire_2", "group": "fire", "weight": 1.0},
    {"id": "water_1", "group": "water", "weight": 1.0},
    {"id": "earth_1", "group": "earth", "weight": 1.0},
]


def make_state(template_id: str = "d_strong", stamina: float = 3.0) -> GameState:
    """构造带一名弟子的存档。"""
    return GameState(
        resources=Resources(stamina=stamina),
        disciples=[DiscipleState(id="d1", template_id=template_id)],
    )


def test_party_power_uses_base_stats() -> None:
    """战力按攻击 + 防御一半 + 气血十分之一计算。"""
    state = make_state()
    assert party_power(state.disciples, TEMPLATES) == pytest.approx(35.0)


def test_start_run_marks_busy_and_costs_stamina() -> None:
    """出发扣行动力、标 busy，并生成第一层候选。"""
    state = make_state()
    assert start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1) is None

    assert state.resources.stamina == pytest.approx(2.0)
    assert state.disciples[0].busy is True
    assert state.active_run is not None
    assert len(state.active_run.choices) == 2
    assert run_status(state.active_run, MODE) == "choosing_node"


def test_start_run_rejects_second_run() -> None:
    """同一时间只能有一支出征队伍。"""
    state = make_state()
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    assert start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=2) == "已有进行中的出征"


def test_start_run_rejects_busy_disciple() -> None:
    """已在出征的弟子不能再入队。"""
    state = make_state()
    state.disciples[0].busy = True
    assert "正在出征" in (start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1) or "")


def test_start_run_rejects_low_stamina() -> None:
    """行动力不足时无法出发。"""
    state = make_state(stamina=0.0)
    assert start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1) == "行动力不足"


def test_same_seed_gives_same_choices() -> None:
    """同种子生成同一组候选节点。"""
    left, right = make_state(), make_state()
    start_run(left, ["d1"], TEMPLATES, MODE, NOW, seed=7)
    start_run(right, ["d1"], TEMPLATES, MODE, NOW, seed=7)

    assert [node.enemy for node in left.active_run.choices] == [
        node.enemy for node in right.active_run.choices
    ]


def test_choose_appends_node_and_deals_damage() -> None:
    """选节点后路线加一、血量下降、战利品入账。"""
    state = make_state()
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    hp_before = state.active_run.hp

    assert choose(state, 0, TEMPLATES, [], MODE, BONDS) is None
    assert len(state.active_run.nodes) == 1
    assert state.active_run.hp < hp_before
    assert state.active_run.pending_loot["cultivation"] > 0


def test_choose_requires_affix_pick() -> None:
    """有待选词条时不能再选节点。"""
    state = make_state()
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    choose(state, 0, TEMPLATES, AFFIXES, MODE, BONDS)

    assert state.active_run.affix_pending is True
    assert run_status(state.active_run, MODE) == "choosing_affix"
    assert choose(state, 0, TEMPLATES, AFFIXES, MODE, BONDS) == "请先选择词条"


def test_pick_affix_advances_choices() -> None:
    """选完词条后生成下一层候选。"""
    state = make_state()
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    choose(state, 0, TEMPLATES, AFFIXES, MODE, BONDS)
    option = state.active_run.affix_options[0]

    assert pick_affix(state, option, MODE) is None
    assert state.active_run.affixes == [option]
    assert state.active_run.affix_pending is False
    assert len(state.active_run.choices) == 2


def test_weak_party_is_defeated() -> None:
    """战力不足时血量归零，状态转为失败。"""
    state = make_state("d_weak")
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    choose(state, 0, TEMPLATES, [], MODE, BONDS)

    assert state.active_run.hp == 0
    assert run_status(state.active_run, MODE) == "defeated"


def test_choose_rejects_after_defeat() -> None:
    """失败后不能再选节点，必须先结算。"""
    state = make_state("d_weak")
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    choose(state, 0, TEMPLATES, [], MODE, BONDS)

    assert "已结束" in (choose(state, 0, TEMPLATES, [], MODE, BONDS) or "")


def test_defeat_settles_half_loot() -> None:
    """失败结算只发一半战利品。"""
    state = make_state("d_weak")
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    state.active_run.pending_loot = {"cultivation": 100.0}
    choose(state, 0, TEMPLATES, [], MODE, BONDS)

    result = settle_run(state, MODE, NOW)

    assert result["victory"] is False
    assert result["loot"]["cultivation"] == pytest.approx(53.0)
    assert state.resources.cultivation == pytest.approx(53.0)
    assert state.active_run is None


def test_clear_settles_full_loot() -> None:
    """通关结算发全部战利品并刷新塔层。"""
    state = make_state()
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)

    state.active_run.nodes = [
        RunNode(kind="battle", enemy=f"battle_{i}", power=1)
        for i in range(MODE["node_count"] - 1)
    ]
    state.active_run.choices = [RunNode(kind="boss", enemy="boss_9", power=1)]
    state.active_run.pending_loot = {"cultivation": 100.0}

    choose(state, 0, TEMPLATES, [], MODE, BONDS)
    result = settle_run(state, MODE, NOW)

    assert result["victory"] is True
    assert result["loot"]["cultivation"] == pytest.approx(150.0)
    assert state.tower_floor == MODE["node_count"]


def test_settle_clears_busy() -> None:
    """结算后弟子解除占用。"""
    state = make_state()
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    state.active_run.hp = 0

    settle_run(state, MODE, NOW)

    assert state.disciples[0].busy is False


def test_same_seed_and_decisions_replay_identically() -> None:
    """同种子 + 同决策序列，两次出征结果一致。"""

    def play(seed: int) -> tuple[int, int]:
        state = make_state()
        start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=seed)
        while run_status(state.active_run, MODE) in {"choosing_node", "choosing_affix"}:
            if state.active_run.affix_pending:
                pick_affix(state, state.active_run.affix_options[0], MODE)
            else:
                choose(state, 0, TEMPLATES, AFFIXES, MODE, BONDS)
        return len(state.active_run.nodes), state.active_run.hp

    assert play(11) == play(11)


def test_node_count_comes_from_mode() -> None:
    """通关层数由模式配置决定，不是写死的。"""
    short = {**MODE, "node_count": 2}
    state = make_state()
    start_run(state, ["d1"], TEMPLATES, short, NOW, seed=1)

    state.active_run.nodes = [RunNode(kind="battle", enemy="battle_0", power=1)]
    state.active_run.choices = [RunNode(kind="boss", enemy="boss_1", power=1)]
    choose(state, 0, TEMPLATES, [], short, BONDS)

    assert run_status(state.active_run, short) == "cleared"


def test_tower_config_has_fields_engine_needs() -> None:
    """仓库里的塔配置包含引擎依赖的全部字段。"""
    from app.config_loader import load_modes

    mode = load_modes()["tower"]
    for field in (
        "id",
        "stamina_cost",
        "node_count",
        "start_hp",
        "base_enemy_power",
        "choices_per_step",
        "elite_chance",
        "rewards",
    ):
        assert field in mode


def test_run_survives_serialization() -> None:
    """出征中途存档再读回，节点、游标与待选词条都不丢，并能继续推进。"""
    state = make_state()
    start_run(state, ["d1"], TEMPLATES, MODE, NOW, seed=1)
    choose(state, 0, TEMPLATES, AFFIXES, MODE, BONDS)
    original_cursor = state.active_run.rng_cursor

    restored = GameState.model_validate_json(state.model_dump_json())

    assert restored.active_run is not None
    assert restored.active_run.rng_cursor == original_cursor
    assert [node.enemy for node in restored.active_run.nodes] == [
        node.enemy for node in state.active_run.nodes
    ]
    assert restored.active_run.affix_options == state.active_run.affix_options

    option = restored.active_run.affix_options[0]
    assert pick_affix(restored, option, MODE) is None
    assert len(restored.active_run.choices) > 0
