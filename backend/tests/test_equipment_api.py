"""隔离数据库验证装备预览只读、CAS 防重与洗练候选恢复。"""

import httpx
import pytest_asyncio
from fastapi import FastAPI

from app.api.equipment import router
from app.db import create_engine, create_session_factory
from app.models.equipment import GearItem
from app.models.save import DiscipleState, GameState
from app.repositories.saves import SaveRepository
from app.repositories.tables import metadata

MATERIAL = "lian_qi_jing_cui"


@pytest_asyncio.fixture
async def equipment_client(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'equipment.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = create_session_factory(engine)
    app = FastAPI()
    app.state.session_factory = factory
    app.include_router(router, prefix="/api")
    item = GearItem(
        id="gear_1", definition_id="qing_feng_blade", name="青锋剑",
        slot="weapon", main_stat="atk", main_value=.08,
        affix="hp", affix_grade=1, affix_value=.02,
    )
    async with factory() as session:
        slot = await SaveRepository(session).create_slot("装备验证", GameState(
            rng_seed=17, equipment_version=1, next_gear_id=2,
            inventory={MATERIAL: 100}, gear={item.id: item},
            disciples=[DiscipleState(id="d1", template_id="huatuo")],
        ))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory, slot
    await engine.dispose()


async def read_saved(factory, slot):
    async with factory() as session:
        repo = SaveRepository(session)
        state, revision = await repo.get_state(slot)
        settled_at = await repo.get_last_settled_at(slot)
        return state.model_dump(), revision, settled_at


async def test_equipment_preview_is_read_only_and_exposes_real_costs(equipment_client):
    client, factory, slot = equipment_client
    before = await read_saved(factory, slot)
    response = await client.get(f"/api/saves/{slot}/equipment")
    assert response.status_code == 200
    data = response.json()
    assert data["revision"] == before[1]
    assert set(data["slots"]) == {"weapon", "armor", "boots", "ring"}
    item = data["items"][0]
    assert item["upgrade_costs"] == {MATERIAL: 2}
    assert item["upgrade_stats"]["atk"] == .088
    assert item["smelt_returns"] == {MATERIAL: 2}
    assert item["unequip_reason"] and item["resolve_reason"]
    assert item["upgradeable"]
    assert await read_saved(factory, slot) == before


async def test_upgrade_commits_cost_once_and_stale_revision_cannot_repeat(equipment_client):
    client, factory, slot = equipment_client
    data = (await client.get(f"/api/saves/{slot}/equipment")).json()
    command = {"revision": data["revision"], "action": "upgrade", "item_id": "gear_1"}
    first = await client.post(f"/api/saves/{slot}/equipment", json=command)
    assert first.status_code == 200
    result = first.json()
    assert result["state"]["gear"]["gear_1"]["level"] == 1
    assert result["state"]["inventory"][MATERIAL] == 98
    assert result["items"][0]["stats"] == data["items"][0]["upgrade_stats"]
    assert (await client.post(f"/api/saves/{slot}/equipment", json=command)).status_code == 409
    state, revision, _ = await read_saved(factory, slot)
    assert revision == result["revision"]
    assert state["gear"]["gear_1"]["level"] == 1
    assert state["inventory"][MATERIAL] == 98


async def test_reforge_result_can_be_queried_after_lost_response_without_repaying(equipment_client):
    client, factory, slot = equipment_client
    before = (await client.get(f"/api/saves/{slot}/equipment")).json()
    rolled = await client.post(f"/api/saves/{slot}/equipment", json={
        "revision": before["revision"], "action": "reforge", "item_id": "gear_1",
    })
    assert rolled.status_code == 200
    result = rolled.json()
    restored = (await client.get(f"/api/saves/{slot}/equipment")).json()
    assert restored["revision"] == result["revision"]
    pending = restored["items"][0]["pending_affix"]
    assert pending == result["items"][0]["pending_affix"]
    state, revision, _ = await read_saved(factory, slot)
    assert state["inventory"][MATERIAL] == 97
    assert state["gear_rng_cursor"] == 4
    again = await client.post(f"/api/saves/{slot}/equipment", json={
        "revision": revision, "action": "reforge", "item_id": "gear_1",
    })
    assert again.status_code == 400
    assert (await read_saved(factory, slot))[0] == state
    resolved = await client.post(f"/api/saves/{slot}/equipment", json={
        "revision": revision, "action": "resolve", "item_id": "gear_1", "keep": False,
    })
    assert resolved.status_code == 200
    item = resolved.json()["state"]["gear"]["gear_1"]
    assert item["affix"] == pending["stat"]
    assert item["affix_grade"] == pending["grade"]
    assert item["affix_value"] == pending["value"]
    assert item["pending_affix"] is None
    assert resolved.json()["state"]["inventory"][MATERIAL] == 97


async def test_lock_blocks_smelt_then_refunds_real_investment_once(equipment_client):
    client, factory, slot = equipment_client
    revision = (await client.get(f"/api/saves/{slot}/equipment")).json()["revision"]

    async def command(action, **extra):
        return await client.post(f"/api/saves/{slot}/equipment", json={
            "revision": revision, "action": action, "item_id": "gear_1", **extra,
        })

    locked = await command("lock", locked=True)
    assert locked.status_code == 200
    revision = locked.json()["revision"]
    before = await read_saved(factory, slot)
    assert (await command("smelt")).status_code == 400
    assert await read_saved(factory, slot) == before
    unlocked = await command("lock", locked=False)
    revision = unlocked.json()["revision"]
    upgraded = await command("upgrade")
    revision = upgraded.json()["revision"]
    smelted = await command("smelt")
    assert smelted.status_code == 200
    revision = smelted.json()["revision"]
    assert smelted.json()["state"]["inventory"][MATERIAL] == 101
    assert smelted.json()["items"] == []
    before = await read_saved(factory, slot)
    assert (await command("smelt")).status_code == 400
    assert await read_saved(factory, slot) == before


async def test_invalid_target_is_atomic_and_equipped_item_cannot_be_smelted(equipment_client):
    client, factory, slot = equipment_client
    revision = (await client.get(f"/api/saves/{slot}/equipment")).json()["revision"]
    before = await read_saved(factory, slot)
    command = {"revision": revision, "action": "equip", "item_id": "gear_1", "disciple_id": "missing"}
    assert (await client.post(f"/api/saves/{slot}/equipment", json=command)).status_code == 400
    assert await read_saved(factory, slot) == before
    response = await client.post(f"/api/saves/{slot}/equipment", json={**command, "disciple_id": "d1"})
    assert response.status_code == 200
    assert response.json()["items"][0]["equipped_by"] == "d1"
    assert response.json()["items"][0]["smelt_reason"]
    assert response.json()["state"]["disciples"][0]["gear_slots"] == {"weapon": "gear_1"}
    assert response.json()["state"]["bonuses"] == {}
    assert (await client.get("/api/saves/99999/equipment")).status_code == 404
