"""隔离数据库验证经济预览不写档、单次命令原子扣费和 revision 防重。"""

import httpx
import pytest_asyncio
from fastapi import FastAPI

from app.api.craft import router as craft_router
from app.api.facilities import router as facilities_router
from app.api.items import router as items_router
from app.db import create_engine, create_session_factory
from app.models.save import DiscipleState, GameState, Resources
from app.repositories.saves import SaveRepository
from app.repositories.tables import metadata


@pytest_asyncio.fixture
async def economy_client(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'economy.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = create_session_factory(engine)
    app = FastAPI()
    app.state.session_factory = factory
    for router in (craft_router, facilities_router, items_router):
        app.include_router(router, prefix="/api")
    async with factory() as session:
        repo = SaveRepository(session)
        slot = await repo.create_slot("经济验证", GameState(
            resources=Resources(spirit_stone=50),
            facility_levels={"hall": 2, "forge": 1, "alchemy": 1, "tower": 1, "training": 1},
            inventory={"ling_cao": 8, "yun_mu": 2, "chi_tong": 6, "qing_shi": 4, "healing_pill": 1},
            disciples=[
                DiscipleState(id="d1", template_id="huatuo", injury_stacks=1),
                DiscipleState(id="d2", template_id="jingwei", injury_stacks=3),
            ],
        ))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory, slot
    await engine.dispose()


async def test_recipe_preview_is_read_only_and_batch_craft_cannot_replay(economy_client):
    client, factory, slot = economy_client
    async with factory() as session:
        before = await SaveRepository(session).get_state(slot)
    response = await client.get(f"/api/saves/{slot}/craft")
    assert response.status_code == 200
    preview = response.json()
    recipe = next(item for item in preview["recipes"] if item["id"] == "liao_shang_dan")
    assert recipe["max_quantity"] == 2
    async with factory() as session:
        after = await SaveRepository(session).get_state(slot)
    assert after == before

    command = {"revision": preview["revision"], "recipe_id": "liao_shang_dan", "quantity": 2}
    crafted = await client.post(f"/api/saves/{slot}/craft", json=command)
    assert crafted.status_code == 200
    assert crafted.json()["inventory"]["liao_shang_dan"] == 2
    assert (await client.post(f"/api/saves/{slot}/craft", json=command)).status_code == 409
    invalid = {**command, "revision": crafted.json()["revision"], "quantity": -1}
    assert (await client.post(f"/api/saves/{slot}/craft", json=invalid)).status_code == 422
    async with factory() as session:
        state, revision = await SaveRepository(session).get_state(slot)
    assert revision == crafted.json()["revision"]
    assert state.inventory["liao_shang_dan"] == 2


async def test_heal_preview_and_execution_share_consumption_and_cas(economy_client):
    client, factory, slot = economy_client
    preview = await client.post(f"/api/saves/{slot}/items/heal-party/preview", json={"party": ["d1", "d2"]})
    assert preview.status_code == 200
    data = preview.json()
    assert data["healed"] == ["d2", "d1"]
    assert data["crafted"] == data["stock_used"] == 1
    async with factory() as session:
        state, revision = await SaveRepository(session).get_state(slot)
    assert revision == data["revision"]
    assert state.disciples[0].injury_stacks == 1
    command = {"revision": revision, "party": ["d1", "d2"]}
    healed = await client.post(f"/api/saves/{slot}/items/heal-party", json=command)
    assert healed.status_code == 200
    result = healed.json()
    assert result["healed"] == data["healed"]
    assert result["costs"] == data["costs"]
    assert all(d["injury_stacks"] == 0 for d in result["state"]["disciples"])
    assert "healing_pill" not in result["state"]["inventory"]
    assert "liao_shang_dan" not in result["state"]["inventory"]
    assert (await client.post(f"/api/saves/{slot}/items/heal-party", json=command)).status_code == 409


async def test_facility_upgrade_uses_preview_costs_once(economy_client):
    client, factory, slot = economy_client
    response = await client.get(f"/api/saves/{slot}/facilities")
    assert response.status_code == 200
    preview = response.json()
    forge = next(item for item in preview["facilities"] if item["id"] == "forge")
    assert forge["upgradeable"]
    command = {"revision": preview["revision"], "facility_id": "forge"}
    response = await client.post(f"/api/saves/{slot}/facilities/upgrade", json=command)
    assert response.status_code == 200
    state = response.json()["state"]
    assert state["facility_levels"]["forge"] == 2
    assert state["inventory"].get("chi_tong", 0) == 0
    assert state["inventory"].get("qing_shi", 0) == 0
    assert (await client.post(f"/api/saves/{slot}/facilities/upgrade", json=command)).status_code == 409


async def test_advanced_pill_legacy_difference_survives_reload_without_replay(economy_client):
    client, factory, slot = economy_client
    async with factory() as session:
        repo = SaveRepository(session)
        state, revision = await repo.get_state(slot)
        state.disciples[0].pill_uses = {"ju_qi_dan": 3}
        state.disciples[0].bonuses = {"atk": .15}
        state.inventory["ju_qi_dan:g2"] = 2
        assert await repo.save_state(slot, state, revision)
    command = {"revision": revision + 1, "item_id": "ju_qi_dan:g2", "target": "d1"}
    used = await client.post(f"/api/saves/{slot}/items/use", json=command)
    assert used.status_code == 200
    assert (await client.post(f"/api/saves/{slot}/items/use", json=command)).status_code == 409
    async with factory() as session:
        state, current = await SaveRepository(session).get_state(slot)
    assert current == used.json()["revision"]
    assert state.disciples[0].bonuses["atk"] == .175
    assert state.disciples[0].pill_grades["ju_qi_dan"] == [2, 1, 1]
    assert state.inventory["ju_qi_dan:g2"] == 1
    again = await client.post(f"/api/saves/{slot}/items/use", json={**command, "revision": current})
    assert again.status_code == 200
    assert round(again.json()["disciple"]["bonuses"]["atk"], 6) == .2
    assert again.json()["disciple"]["pill_uses"]["ju_qi_dan"] == 3
