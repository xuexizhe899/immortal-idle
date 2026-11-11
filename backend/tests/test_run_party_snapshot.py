"""挂机自然消伤不能改变同一局的战斗输入，旧档恢复不消耗随机游标。"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import update

from app.api.state import commit_mutation, prepare_mutation, snapshot
from app.config_loader import load_affixes, load_bonds, load_disciples, load_modes
from app.domain.run_engine import choose, pick_affix, run_status, start_run
from app.domain.settle import settle
from app.models.save import DiscipleState, GameState, Resources
from app.repositories.saves import SaveRepository
from app.repositories.tables import save_slots
from tests.test_gameplay_api import game_client

T0 = datetime(2026, 11, 11, tzinfo=timezone.utc)


def injured_state() -> GameState:
    return GameState(
        resources=Resources(stamina=3), bonuses={"atk": .15},
        disciples=[
            DiscipleState(
                id=template, template_id=template, level=2, realm=2,
                injury_stacks=1, injured_until=T0 + timedelta(hours=4),
            )
            for template in ("guanyu", "zhangfei", "zhaoyun")
        ],
    )


def test_natural_healing_and_permanent_changes_do_not_change_run_replay():
    templates, bonds, affixes = load_disciples(), load_bonds(), load_affixes()
    mode = load_modes()["tower"]
    immediate = injured_state()
    assert start_run(
        immediate, [d.id for d in immediate.disciples], templates, mode, T0,
        seed=61, bonds=bonds,
    ) is None
    # 模拟重启、四小时后回来：永久层自然消伤，本局保持出发时的折扣。
    delayed = GameState.model_validate_json(immediate.model_dump_json())
    settle(delayed, T0, T0 + timedelta(hours=4))
    assert all(d.injury_stacks == 0 for d in delayed.disciples)
    delayed.disciples[0].level = 100
    delayed.bonuses["atk"] = 100
    original_snapshot = immediate.active_run.party_snapshot
    assert original_snapshot == delayed.active_run.party_snapshot
    while run_status(immediate.active_run, mode) not in {"cleared", "defeated"}:
        if immediate.active_run.affix_pending:
            choice = immediate.active_run.affix_options[0]
            assert choice in delayed.active_run.affix_options
            assert pick_affix(immediate, choice, mode) is None
            assert pick_affix(delayed, choice, mode) is None
        else:
            assert choose(immediate, 0, templates, affixes, mode, bonds) is None
            assert choose(delayed, 0, templates, affixes, mode, bonds) is None
            assert immediate.active_run.last_battle == delayed.active_run.last_battle
    assert immediate.active_run == delayed.active_run
    # 数字和元组都被冻结，且不引用永久层对象。
    with pytest.raises(ValidationError):
        original_snapshot.combatants[0].attack = 999


def test_snapshot_keeps_stats_and_bonds_when_configuration_changes():
    templates = load_disciples()
    bonds = load_bonds()
    state = injured_state()
    mode = load_modes()["tower"]
    start_run(state, [d.id for d in state.disciples], templates, mode, T0, seed=1, bonds=bonds)
    expected = GameState.model_validate_json(state.model_dump_json())
    changed = {
        key: {**template, "base_stats": {"atk": 1, "hp": 1, "def": 1, "spd": 1}}
        for key, template in templates.items()
    }
    choose(expected, 0, templates, [], mode, bonds)
    choose(state, 0, changed, [], mode, {})
    assert state.active_run.last_battle == expected.active_run.last_battle


async def test_legacy_run_captures_before_idle_healing_and_preserves_rng(game_client):
    _, factory = game_client
    state = injured_state()
    for disciple in state.disciples:
        disciple.injured_until = datetime.now(timezone.utc) - timedelta(hours=1)
    mode = load_modes()["tower"]
    templates, bonds = load_disciples(), load_bonds()
    start_run(state, [d.id for d in state.disciples], templates, mode, T0, seed=3, bonds=bonds)
    expected_snapshot = state.active_run.party_snapshot
    expected_cursor = state.active_run.rng_cursor
    raw = state.model_dump(mode="json")
    del raw["active_run"]["party_snapshot"]
    legacy = GameState.model_validate(raw)
    assert legacy.active_run.party_snapshot is None
    # 读取只生成兼容展示快照，不推进节点或随机数。
    read = snapshot(legacy.model_copy(deep=True), 1)
    assert read.state.active_run.party_snapshot == expected_snapshot
    assert read.state.active_run.rng_cursor == expected_cursor
    async with factory() as session:
        repo = SaveRepository(session)
        slot = await repo.create_slot("旧出征", legacy)
        await session.execute(update(save_slots).where(save_slots.c.slot_id == slot).values(
            last_settled_at=(datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
        ))
        await session.commit()
        command = await prepare_mutation(slot, repo, 1)
        assert all(d.injury_stacks == 0 for d in command.state.disciples)
        assert command.state.active_run.party_snapshot == expected_snapshot
        assert command.state.active_run.rng_cursor == expected_cursor
        assert command.state.active_run.nodes == []
        await commit_mutation(slot, command, repo)
        restored, _ = await repo.get_state(slot)
        assert restored.active_run.party_snapshot == expected_snapshot

