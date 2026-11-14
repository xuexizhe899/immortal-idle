"""生产专长、跨岗调度和旧收益补算的回归。"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio

from app.config_loader import load_enemies, load_sects
from app.domain.conquest import ensure_sects
from app.domain.deployment import assign_garrison, detach_for_run, restore_after_run
from app.domain.duty import assign, garrison_production, rates_of, record_event
from app.domain.settle import material_production, settle
from app.models.save import DiscipleState, DutySlot, GameState

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
TEMPLATES = {
    "worker": {"lean": "attack", "rarity": 1, "production_specialty": "han_tie"},
    "general": {"lean": "attack", "rarity": 3, "production_specialty": "ling_cao"},
    "special": {"lean": "support", "rarity": 1, "production_specialty": "gong_fa_qi_pei"},
}


def world():
    state = GameState(rng_seed=42, disciples=[
        DiscipleState(id="a", template_id="worker"),
        DiscipleState(id="b", template_id="general"),
        DiscipleState(id="c", template_id="special"),
    ])
    ensure_sects(state, load_sects(), load_enemies())
    state.sects[0].conquered = True
    return state


def test_low_rarity_specialist_outproduces_general_for_its_material():
    state = world()
    assert assign(state, "a", TEMPLATES, NOW) is None
    specialist = material_production(rates_of(state, TEMPLATES))
    state.duty_slots = [DutySlot(disciple_id="b", assigned_at=NOW)]
    general = material_production(rates_of(state, TEMPLATES))
    assert specialist["han_tie"] == pytest.approx(0.5)
    assert general["han_tie"] == pytest.approx(0.25)
    assert general["ling_cao"] > specialist["ling_cao"]


def test_training_upgrade_only_changes_new_interval():
    state = world()
    assign(state, "a", TEMPLATES, NOW)
    state.facility_levels["training"] = 3
    record_event(state, TEMPLATES, NOW + timedelta(hours=1))
    report = settle(state, NOW, NOW + timedelta(hours=3))
    # 一级两倍基础寒铁时产0.5，三级1.5倍专长增量时产0.625。
    assert report.materials["han_tie"] == 1
    assert state.material_remainders["han_tie"] == pytest.approx(0.75)
    assert report.cultivation == pytest.approx(1.05 + 2 * 1.075)


def test_garrison_adds_each_member_and_capped_idle_uses_actual_rates():
    state = world()
    sect = state.sects[0]
    for disciple_id in ("a", "b", "c"):
        assert assign_garrison(state, sect.id, disciple_id, NOW) is None
    outputs = garrison_production(state, TEMPLATES)[sect.id]
    assert outputs["han_tie"] == pytest.approx(2.0)
    assert outputs["gong_fa_qi_pei"] == pytest.approx(0.6)
    record_event(state, TEMPLATES, NOW)
    report = settle(state, NOW, NOW + timedelta(hours=20))
    assert report.elapsed_hours == 12
    assert report.materials["gong_fa_qi_pei"] == 7
    assert state.material_remainders["gong_fa_qi_pei"] == pytest.approx(0.2)


def test_transfer_is_exclusive_and_failed_transfer_keeps_old_job():
    state = world()
    assert assign(state, "a", TEMPLATES, NOW) is None
    assert assign_garrison(state, state.sects[0].id, "a", NOW) is None
    assert state.duty_slots == []
    assert assign_garrison(state, state.sects[1].id, "a", NOW) is not None
    assert state.sects[0].garrison[0].disciple_id == "a"
    assert assign(state, "a", TEMPLATES, NOW) is None
    assert state.sects[0].garrison == []
    assert [slot.disciple_id for slot in state.duty_slots] == ["a"]


def test_departure_and_return_do_not_evict_existing_workers():
    state = world()
    assign(state, "a", TEMPLATES, NOW)
    assign_garrison(state, state.sects[0].id, "b", NOW)
    posts = detach_for_run(state, ["a", "b"])
    assert posts == {"a": "home", "b": state.sects[0].id}
    assert state.duty_slots == state.sects[0].garrison == []
    state.duty_slots = [DutySlot(disciple_id=f"other{i}", assigned_at=NOW) for i in range(6)]
    assert restore_after_run(state, posts, NOW) == ["a"]
    assert len(state.duty_slots) == 6
    assert state.sects[0].garrison[0].disciple_id == "b"


def test_special_materials_require_external_post_and_stop_on_departure():
    state = world()
    assign(state, "c", TEMPLATES, NOW)
    assert material_production(rates_of(state, TEMPLATES))["gong_fa_qi_pei"] == 0
    assign_garrison(state, state.sects[0].id, "c", NOW)
    record_event(state, TEMPLATES, NOW)
    detach_for_run(state, ["c"])
    record_event(state, TEMPLATES, NOW + timedelta(hours=5))
    report = settle(state, NOW, NOW + timedelta(hours=10))
    assert report.materials["gong_fa_qi_pei"] == 1
    assert state.material_remainders["gong_fa_qi_pei"] == pytest.approx(0.5)


@pytest_asyncio.fixture
async def client_and_factory(tmp_path):
    from app.db import create_engine, create_session_factory
    from app.main import app
    from app.repositories.tables import metadata
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'garrison.db').as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    factory = create_session_factory(engine)
    app.state.session_factory = factory
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory
    await engine.dispose()


async def test_legacy_world_is_saved_once_and_reads_do_not_reroll(client_and_factory):
    from app.repositories.saves import SaveRepository
    client, factory = client_and_factory
    async with factory() as session:
        slot = await SaveRepository(session).create_slot("旧档", GameState())
    first = await client.get(f"/api/saves/{slot}")
    assert first.status_code == 200
    first = first.json()
    second = (await client.get(f"/api/saves/{slot}")).json()
    assert first["state"]["sects"] == second["state"]["sects"]
    assert len(second["state"]["sects"]) == 3
    assert first["revision"] == second["revision"] == 2
    assert second["state"]["resources"]["reputation"] == 0


async def test_garrison_command_cas_and_busy_protection(client_and_factory):
    from app.repositories.saves import SaveRepository
    client, factory = client_and_factory
    state = world()
    state.disciples[0].template_id = "jingwei"
    async with factory() as session:
        slot = await SaveRepository(session).create_slot("驻守", state)
    request = {"revision": 1, "sect_id": state.sects[0].id, "disciple_id": "a"}
    response = await client.post(f"/api/saves/{slot}/garrison/assign", json=request)
    assert response.status_code == 200
    assert response.json()["production"]["garrisons"][state.sects[0].id]["han_tie"] > 0
    assert (await client.post(f"/api/saves/{slot}/garrison/assign", json=request)).status_code == 409
    async with factory() as session:
        repo = SaveRepository(session)
        latest, revision = await repo.get_state(slot)
        latest.disciples[1].busy = True
        assert await repo.save_state(slot, latest, revision)
    response = await client.post(f"/api/saves/{slot}/garrison/assign", json={**request, "revision": revision + 1, "disciple_id": "b"})
    assert response.status_code == 400
