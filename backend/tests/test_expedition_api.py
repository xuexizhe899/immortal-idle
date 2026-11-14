"""远行码头模式参数、快照固化与独立进度回归。"""

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
from app.domain.run_engine import settle_run, start_run
from app.main import app
from app.models.save import DiscipleState, GameState, Resources, RunNode
from app.repositories import saves as save_repository
from app.repositories.tables import metadata


@pytest_asyncio.fixture
async def expedition_client(tmp_path, monkeypatch):
    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 14, tzinfo=timezone.utc)

    # 固定命令与存档时钟，收益断言不混入测试执行时长产生的挂机产出。
    monkeypatch.setattr(state_api, "datetime", FixedClock)
    monkeypatch.setattr(save_repository, "utcnow", FixedClock.now)
    monkeypatch.setattr(run_api.run_engine.secrets, "randbits", lambda bits: 7)
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'expedition.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = create_session_factory(engine)
    monkeypatch.setattr(app.state, "session_factory", factory, raising=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        yield client
    await engine.dispose()


async def import_party(client: httpx.AsyncClient, *, weak=False) -> tuple[int, list[str]]:
    party = ["guanyu"] if weak else ["guanyu", "zhangfei", "zhaoyun", "zhugeliang", "yuefei", "baisuzhen"]
    state = GameState(
        resources=Resources(stamina=4),
        disciples=[DiscipleState(id=key, template_id=key, level=1 if weak else 10, realm=1 if weak else 3) for key in party],
    )
    response = await client.post("/api/saves/import", json={
        "name": "远行测试", "schema_version": 1, "state": state.model_dump(mode="json"),
    })
    assert response.status_code == 201
    return response.json()["slot_id"], party


async def test_catalog_exposes_only_enabled_expedition_mode(expedition_client):
    response = await expedition_client.get("/api/catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"]["id"] == "tower"
    assert body["modes"]["expedition"]["node_count"] == 12
    assert "invasion" not in body["modes"]


async def test_expedition_start_uses_saved_mode_and_real_route(expedition_client):
    slot, party = await import_party(expedition_client)
    response = await expedition_client.post(f"/api/saves/{slot}/run/start", json={
        "revision": 1, "party": party, "mode": "expedition",
    })
    assert response.status_code == 200
    body = response.json()
    run = body["run"]
    assert run["mode"] == "expedition"
    assert run["party_snapshot"]["mode"]["id"] == "expedition"
    assert run["party_snapshot"]["route_version"] == 2
    assert run["choices"]
    assert all(node["enemies"] and node["reward"] for node in run["choices"])
    assert body["state"]["resources"]["stamina"] == pytest.approx(2, abs=0.01)
    assert body["state"]["expedition_floor"] == 0


def test_expedition_settlement_updates_only_expedition_record():
    party = ["guanyu", "zhangfei", "zhaoyun"]
    state = GameState(
        resources=Resources(stamina=4),
        disciples=[DiscipleState(id=key, template_id=key, level=10, realm=3) for key in party],
    )
    mode = deepcopy(load_modes()["expedition"])
    assert start_run(
        state, party, load_disciples(), mode, datetime(2026, 11, 14, tzinfo=timezone.utc),
        seed=3, enemies=deepcopy(load_enemies()), route_version=2,
    ) is None
    run = state.active_run
    run.nodes = [RunNode(kind="battle", enemy="battle_0", enemies=["stone_guard"], power=1, reward={})] * mode["node_count"]
    run.choices = []
    result = settle_run(state, mode, datetime(2026, 11, 14, tzinfo=timezone.utc))
    assert result["victory"] is True
    assert state.expedition_floor == mode["node_count"]
    assert state.tower_floor == 0
    assert state.active_run is None


async def test_complete_expedition_uses_snapshot_after_live_mode_is_removed(expedition_client, monkeypatch):
    client = expedition_client
    slot, party = await import_party(client)
    started = await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": 1, "party": party, "mode": "expedition",
    })
    assert started.status_code == 200
    body = started.json()
    frozen_mode = body["run"]["party_snapshot"]["mode"]
    # 已出发的十二段路线和结算不依赖随后移除的实时模式。
    monkeypatch.setattr(run_api, "load_modes", lambda: {})
    battles = affixes = 0
    while body["status"] not in {"cleared", "defeated"}:
        assert battles < 13 and affixes < 12
        if body["status"] == "choosing_affix":
            endpoint = "affix"
            payload = {"affix_id": body["run"]["affix_options"][0]}
            affixes += 1
        else:
            endpoint = "choose"
            payload = {"choice": 0}
            battles += 1
        response = await client.post(f"/api/saves/{slot}/run/{endpoint}", json={
            "revision": body["revision"], **payload,
        })
        assert response.status_code == 200
        body = response.json()
        assert body["run"]["party_snapshot"]["mode"] == frozen_mode
    assert body["status"] == "cleared"
    assert (battles, affixes) == (12, 11)
    assert body["battle_result"]["node"]["kind"] == "boss"
    pending = body["run"]["pending_loot"]
    before_resources = body["state"]["resources"]
    before_inventory = body["state"]["inventory"]
    ended_revision = body["revision"]

    settlements = await asyncio.gather(*[
        client.post(f"/api/saves/{slot}/run/settle", json={"revision": ended_revision})
        for _ in range(2)
    ])
    assert sorted(response.status_code for response in settlements) == [200, 409]
    settled = next(response for response in settlements if response.status_code == 200)
    result = settled.json()
    state = result["state"]
    assert result["victory"] is True
    assert state["active_run"] is None and state["expedition_floor"] == 12 and state["tower_floor"] == 0
    assert all(not disciple["busy"] and disciple["injury_stacks"] == 0 for disciple in state["disciples"])
    for key, amount in result["loot"].items():
        if key in before_resources:
            assert amount == pending[key]
            assert state["resources"][key] == pytest.approx(before_resources[key] + amount)
        else:
            assert amount == int(pending[key])
            assert state["inventory"][key] == before_inventory.get(key, 0) + amount
    review = state["last_run_review"]
    assert review["mode"] == "expedition" and review["victory"] is True
    assert review["cleared"] == review["total_nodes"] == 12
    assert review["loot"] == result["loot"]
    assert review["last_battle"]["node"] == body["battle_result"]["node"]
    assert len(review["last_battle"]["key_actions"]) <= 3

    replay = await client.post(f"/api/saves/{slot}/run/settle", json={"revision": ended_revision})
    assert replay.status_code == 409
    duplicate = await client.post(f"/api/saves/{slot}/run/settle", json={"revision": result["revision"]})
    assert duplicate.status_code == 400
    for _ in range(2):
        refreshed = (await client.get(f"/api/saves/{slot}")).json()
        assert refreshed["state"] == state
        assert refreshed["revision"] == result["revision"]


@pytest.mark.parametrize("mode,availability,status", [
    ("invasion", "enabled", 422), ("unknown", "enabled", 422),
    ("expedition", "disabled", 400), ("expedition", "missing", 400),
])
async def test_unavailable_modes_do_not_consume_or_change_state(expedition_client, monkeypatch, mode, availability, status):
    slot, party = await import_party(expedition_client)
    modes = deepcopy(load_modes())
    if availability == "disabled":
        modes["expedition"]["enabled"] = False
    elif availability == "missing":
        del modes["expedition"]
    monkeypatch.setattr(run_api, "load_modes", lambda: modes)
    before = (await expedition_client.get(f"/api/saves/{slot}")).json()
    response = await expedition_client.post(f"/api/saves/{slot}/run/start", json={
        "revision": before["revision"], "party": party, "mode": mode,
    })
    assert response.status_code == status
    assert (await expedition_client.get(f"/api/saves/{slot}")).json() == before


async def test_defeated_expedition_persists_review_without_repeating_loot(expedition_client):
    client = expedition_client
    slot, party = await import_party(client, weak=True)
    started = await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": 1, "party": party, "mode": "expedition",
    })
    assert started.status_code == 200
    revision = started.json()["revision"]
    # 当前出征占用所有模式入口；旧版本重放也不能再扣行动力。
    for target, expected_revision, expected_status in (("tower", revision, 400), ("expedition", 1, 409)):
        denied = await client.post(f"/api/saves/{slot}/run/start", json={
            "revision": expected_revision, "party": party, "mode": target,
        })
        assert denied.status_code == expected_status
    rejected = await client.post(f"/api/saves/{slot}/run/settle", json={"revision": revision})
    assert rejected.status_code == 400
    chosen = await client.post(f"/api/saves/{slot}/run/choose", json={"revision": revision, "choice": 0})
    assert chosen.status_code == 200
    ended = chosen.json()
    assert ended["status"] == "defeated" and ended["run"]["hp"] == 0
    stale = await client.post(f"/api/saves/{slot}/run/choose", json={"revision": revision, "choice": 0})
    assert stale.status_code == 409
    assert (await client.get(f"/api/saves/{slot}/run")).json() == ended
    settled = await client.post(f"/api/saves/{slot}/run/settle", json={"revision": ended["revision"]})
    assert settled.status_code == 200
    result = settled.json()
    review = result["state"]["last_run_review"]
    assert review["victory"] is False and review["end_reason"] == "defeated"
    assert review["cleared"] == 1 and review["total_nodes"] == 12
    assert review["loot"] == result["loot"] == {"cultivation": 4.0, "reputation": 1.0}
    assert review["last_battle"]["first_down_id"] == party[0]
    assert review["last_battle"]["surviving_enemies"]
    assert result["state"]["disciples"][0]["injury_stacks"] == 1
    assert result["state"]["resources"]["stamina"] == 2
    exported = (await client.get(f"/api/saves/{slot}/export")).json()
    imported = await client.post("/api/saves/import", json=exported)
    assert imported.status_code == 201
    restored = (await client.get(f"/api/saves/{imported.json()['slot_id']}")).json()
    assert restored["state"] == result["state"]
    assert restored["state"]["last_run_review"] == review

    saved = await client.post(f"/api/saves/{slot}/snapshots", json={"reason": "保留远行复盘"})
    assert saved.status_code == 201
    next_started = await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": result["revision"], "party": party, "mode": "tower",
    })
    assert next_started.status_code == 200
    assert next_started.json()["state"]["last_run_review"] == review
    next_battle = await client.post(f"/api/saves/{slot}/run/choose", json={
        "revision": next_started.json()["revision"], "choice": 0,
    })
    assert next_battle.status_code == 200 and next_battle.json()["status"] == "defeated"
    next_settled = await client.post(f"/api/saves/{slot}/run/settle", json={"revision": next_battle.json()["revision"]})
    assert next_settled.status_code == 200
    assert next_settled.json()["state"]["last_run_review"]["mode"] == "tower"
    # 每次结算仅覆盖本档最近摘要；另一档与恢复到旧快照的事实保持原样。
    assert (await client.get(f"/api/saves/{imported.json()['slot_id']}")).json()["state"] == restored["state"]
    rollback = await client.post(f"/api/saves/{slot}/rollback/{saved.json()['snapshot_id']}")
    assert rollback.status_code == 200
    assert (await client.get(f"/api/saves/{slot}")).json()["state"] == result["state"]
