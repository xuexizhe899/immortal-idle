"""宗门征讨接口：原子开局、逐轮选人、刷新续战与旧远征快照恢复。"""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone

import httpx
import pytest
import pytest_asyncio

from app.api import run as run_api
from app.api import state as state_api
from app.config_loader import load_disciples, load_enemies, load_modes
from app.db import create_engine, create_session_factory
from app.domain.run_engine import start_run
from app.main import app
from app.models.save import DiscipleState, GameState, Resources
from app.repositories import saves as save_repository
from app.repositories.tables import metadata

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
PARTY = ["guanyu", "zhangfei", "zhaoyun", "zhugeliang", "yuefei", "baisuzhen"]


@pytest_asyncio.fixture
async def expedition_client(tmp_path, monkeypatch):
    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(state_api, "datetime", FixedClock)
    monkeypatch.setattr(save_repository, "utcnow", FixedClock.now)
    monkeypatch.setattr(run_api.secrets, "randbits", lambda bits: 7)
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'expedition.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = create_session_factory(engine)
    monkeypatch.setattr(app.state, "session_factory", factory, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await engine.dispose()


async def import_party(client, state=None):
    state = state or GameState(resources=Resources(stamina=4), disciples=[
        DiscipleState(id=key, template_id=key, level=20, realm=3) for key in PARTY
    ])
    response = await client.post("/api/saves/import", json={
        "name": "征讨测试", "schema_version": 1, "state": state.model_dump(mode="json"),
    })
    assert response.status_code == 201
    return response.json()["slot_id"]


async def test_catalog_and_world_expose_conquest(expedition_client):
    client = expedition_client
    catalog = (await client.get("/api/catalog")).json()
    assert catalog["modes"]["expedition"]["node_count"] == 4
    assert catalog["modes"]["expedition"]["name"] == "宗门征讨"
    assert "invasion" not in catalog["modes"]
    slot = await import_party(client)
    response = await client.get(f"/api/saves/{slot}")
    assert response.status_code == 200 and len(response.json()["state"]["sects"]) == 3
    assert (await client.get(f"/api/saves/{slot}")).json() == response.json()


async def test_start_requires_target_and_does_not_mutate_on_invalid_party(expedition_client):
    client = expedition_client
    slot = await import_party(client)
    before = (await client.get(f"/api/saves/{slot}")).json()
    for extra in ({}, {"sect_id": "missing"}, {"sect_id": "sect_1", "party": PARTY[:2]}):
        response = await client.post(f"/api/saves/{slot}/run/start", json={
            "revision": before["revision"], "party": PARTY, "mode": "expedition", **extra,
        })
        assert response.status_code == 400
        assert (await client.get(f"/api/saves/{slot}")).json() == before


async def test_complete_conquest_freezes_target_and_awards_exactly_once(expedition_client, monkeypatch):
    client = expedition_client
    slot = await import_party(client)
    response = await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": 1, "party": PARTY, "mode": "expedition", "sect_id": "sect_1",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["state"]["resources"]["stamina"] == 2
    assert not body["run"]["choices"] and not body["run"]["affix_options"]
    frozen = body["run"]["party_snapshot"]
    monkeypatch.setattr(run_api, "load_modes", lambda: {})
    for members in (PARTY[:3], PARTY[3:], PARTY[:3]):
        response = await client.post(f"/api/saves/{slot}/run/arena", json={"party": members, "revision": body["revision"]})
        assert response.status_code == 200
        body = response.json()
        assert body["run"]["party_snapshot"] == frozen
        assert (await client.get(f"/api/saves/{slot}/run")).json() == body
    assert body["status"] == "cleared" and body["run"]["arena_round"] == 2
    assert body["run"]["guard"] == 0
    assert len([unit for unit in body["battle_result"]["initial_units"] if unit["side"] == "enemy"]) == 1
    assert not body["state"]["sects"][0]["conquered"]
    responses = await asyncio.gather(*[
        client.post(f"/api/saves/{slot}/run/settle", json={"revision": body["revision"]}) for _ in range(2)
    ])
    assert sorted(response.status_code for response in responses) == [200, 409]
    settled = next(response.json() for response in responses if response.status_code == 200)
    assert settled["victory"] and settled["state"]["sects"][0]["conquered"]
    assert settled["state"]["active_run"] is None
    assert settled["loot"] == body["run"]["pending_loot"]
    assert settled["state"]["resources"]["reputation"] == settled["loot"]["reputation"]
    assert all(not d["busy"] for d in settled["state"]["disciples"])
    response = await client.post(f"/api/saves/{slot}/run/settle", json={"revision": settled["revision"]})
    assert response.status_code == 400


async def test_retreat_is_cas_safe_and_cannot_award_or_injure_unused_reserves(expedition_client):
    client = expedition_client
    slot = await import_party(client)
    body = (await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": 1, "party": PARTY, "mode": "expedition", "sect_id": "sect_1",
    })).json()
    revision = body["revision"]
    fought = await client.post(f"/api/saves/{slot}/run/arena", json={"revision": revision, "party": PARTY[:3]})
    assert fought.status_code == 200
    body = fought.json()
    assert (await client.post(f"/api/saves/{slot}/run/arena", json={"revision": revision, "party": PARTY[:3]})).status_code == 409
    assert (await client.post(f"/api/saves/{slot}/run/choose", json={"revision": body["revision"], "choice": 0})).status_code == 400
    body = (await client.post(f"/api/saves/{slot}/run/retreat", json={"revision": body["revision"]})).json()
    assert body["status"] == "defeated" and body["run"]["end_reason"] == "retreated"
    body = (await client.post(f"/api/saves/{slot}/run/settle", json={"revision": body["revision"]})).json()
    assert not body["loot"] and not body["state"]["sects"][0]["conquered"]
    assert [d["injury_stacks"] for d in body["state"]["disciples"]] == [1, 1, 1, 0, 0, 0]
    retry = await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": body["revision"], "party": PARTY, "mode": "expedition", "sect_id": "sect_1",
    })
    assert retry.status_code == 200 and retry.json()["run"]["guard"] == 100


async def test_legacy_expedition_continues_its_frozen_route(expedition_client, monkeypatch):
    state = GameState(resources=Resources(stamina=4), disciples=[
        DiscipleState(id=key, template_id=key, level=20, realm=3) for key in PARTY
    ])
    legacy_mode = deepcopy(load_modes()["expedition"])
    legacy_mode.update(node_count=12, boss_every=12, name="远行")
    assert start_run(state, PARTY, load_disciples(), legacy_mode, NOW, seed=3, enemies=deepcopy(load_enemies()), route_version=2) is None
    slot = await import_party(expedition_client, state)
    monkeypatch.setattr(run_api, "load_modes", lambda: {})
    body = (await expedition_client.get(f"/api/saves/{slot}/run")).json()
    while body["status"] not in {"cleared", "defeated"}:
        assert len(body["run"]["nodes"]) < 13
        if body["status"] == "choosing_affix":
            action, payload = "affix", {"affix_id": body["run"]["affix_options"][0]}
        else:
            action, payload = "choose", {"choice": 0}
        response = await expedition_client.post(f"/api/saves/{slot}/run/{action}", json={"revision": body["revision"], **payload})
        assert response.status_code == 200
        body = response.json()
    assert body["status"] == "cleared" and len(body["run"]["nodes"]) == 12
    response = await expedition_client.post(f"/api/saves/{slot}/run/settle", json={"revision": body["revision"]})
    assert response.status_code == 200
    assert response.json()["state"]["expedition_floor"] == 12
    assert response.json()["state"]["tower_floor"] == 0
    assert not any(sect["conquered"] for sect in response.json()["state"]["sects"])


@pytest.mark.parametrize("mode,availability,status", [
    ("invasion", "enabled", 422), ("unknown", "enabled", 422),
    ("expedition", "disabled", 400), ("expedition", "missing", 400),
])
async def test_unavailable_modes_do_not_consume_or_change_state(expedition_client, monkeypatch, mode, availability, status):
    slot = await import_party(expedition_client)
    modes = deepcopy(load_modes())
    if availability == "disabled":
        modes["expedition"]["enabled"] = False
    elif availability == "missing":
        del modes["expedition"]
    monkeypatch.setattr(run_api, "load_modes", lambda: modes)
    before = (await expedition_client.get(f"/api/saves/{slot}")).json()
    response = await expedition_client.post(f"/api/saves/{slot}/run/start", json={
        "revision": before["revision"], "party": PARTY, "mode": mode, "sect_id": "sect_1",
    })
    assert response.status_code == status
    assert (await expedition_client.get(f"/api/saves/{slot}")).json() == before
