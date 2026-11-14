"""问道塔路线经 API 持久化、版本防重、导入恢复与旧局续玩的集成回归。"""

from copy import deepcopy

import httpx
import pytest_asyncio

from app.api import run as run_api
from app.config_loader import load_enemies, load_modes
from app.db import create_engine, create_session_factory
from app.domain import run_engine
from app.main import app
from app.models.save import DiscipleState, GameState, Resources
from app.repositories.saves import SaveRepository
from app.repositories.tables import metadata


@pytest_asyncio.fixture
async def route_client(tmp_path, monkeypatch):
    """所有操作只写临时文件库，并固定新局种子以便比较恢复前后的战报。"""
    monkeypatch.setattr(run_engine.secrets, "randbits", lambda bits: 1)
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'routes.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = create_session_factory(engine)
    monkeypatch.setattr(app.state, "session_factory", factory, raising=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        yield client, factory
    await engine.dispose()


async def start_route(client):
    """导入明确的满培养测试队伍，避免接口恢复测试被首层战败打断。"""
    party = ["guanyu", "zhangfei", "zhaoyun", "zhugeliang", "yuefei", "baisuzhen"]
    state = GameState(
        resources=Resources(stamina=3),
        disciples=[DiscipleState(id=key, template_id=key, level=10, realm=3) for key in party],
    )
    imported = await client.post("/api/saves/import", json={
        "name": "T22 路线测试", "schema_version": 1, "state": state.model_dump(mode="json"),
    })
    assert imported.status_code == 201
    slot = imported.json()["slot_id"]
    started = await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": 1, "party": party,
    })
    assert started.status_code == 200
    return slot, started.json()


async def test_route_candidates_survive_refresh_and_snapshot_restore(route_client):
    """读取与恢复快照保留候选顺序、编成、奖励及随机游标，重走产生同一战报。"""
    client, _ = route_client
    slot, started = await start_route(client)
    original = started["run"]
    assert original["party_snapshot"]["route_version"] == 2
    assert original["choices"]
    assert all(node["enemies"] for node in original["choices"])
    signatures = [
        (node["kind"], tuple(node["enemies"]), tuple(sorted(node["reward"].items())))
        for node in original["choices"]
    ]
    assert len(signatures) == len(set(signatures))
    for path in (f"/api/saves/{slot}/run", f"/api/saves/{slot}"):
        refreshed = await client.get(path)
        assert refreshed.status_code == 200
        body = refreshed.json()
        assert body["state"]["active_run"] == original
        assert body["revision"] == started["revision"]

    saved = await client.post(f"/api/saves/{slot}/snapshots", json={"reason": "路线恢复回归"})
    assert saved.status_code == 201
    first = await client.post(f"/api/saves/{slot}/run/choose", json={
        "revision": started["revision"], "choice": 0,
    })
    assert first.status_code == 200
    restored = await client.post(f"/api/saves/{slot}/rollback/{saved.json()['snapshot_id']}")
    assert restored.status_code == 200
    content = (await client.get(f"/api/saves/{slot}/run")).json()
    assert content["run"] == original
    assert content["revision"] > first.json()["revision"]
    replay = await client.post(f"/api/saves/{slot}/run/choose", json={
        "revision": content["revision"], "choice": 0,
    })
    assert replay.status_code == 200
    assert replay.json()["run"] == first.json()["run"]


async def test_stale_route_choice_does_not_repeat_rewards_or_advance_rng(route_client):
    """同一版本的选择请求只能成功一次，迟到重发不能扣资源或再发一次奖励。"""
    client, factory = route_client
    slot, started = await start_route(client)
    selected = started["run"]["choices"][0]
    decision = {"revision": started["revision"], "choice": 0}
    first = await client.post(f"/api/saves/{slot}/run/choose", json=decision)
    assert first.status_code == 200
    result = first.json()
    assert result["battle_result"]["won"] is True
    assert result["battle_result"]["node"] == selected
    assert result["battle_result"]["loot"] == selected["reward"]
    assert result["run"]["pending_loot"] == selected["reward"]
    assert [
        unit["template_id"] for unit in result["battle_result"]["initial_units"]
        if unit["side"] == "enemy"
    ] == selected["enemies"]
    async with factory() as session:
        anchor = await SaveRepository(session).get_last_settled_at(slot)

    repeated = await client.post(f"/api/saves/{slot}/run/choose", json=decision)

    assert repeated.status_code == 409
    refreshed = (await client.get(f"/api/saves/{slot}/run")).json()
    assert refreshed == result
    async with factory() as session:
        assert await SaveRepository(session).get_last_settled_at(slot) == anchor


async def test_exported_route_uses_frozen_enemies_after_configuration_changes(route_client, monkeypatch):
    """导出后替换全局编成、敌人数值和奖励，原档与导入档仍执行相同的本局节点。"""
    client, _ = route_client
    slot, started = await start_route(client)
    exported = await client.get(f"/api/saves/{slot}/export")
    assert exported.status_code == 200
    selected = started["run"]["choices"][0]
    modes = deepcopy(load_modes())
    modes["tower"]["encounter_variants"] = {
        kind: [["tower_master"]] for kind in ("battle", "elite", "boss")
    }
    modes["tower"]["rewards"] = {
        kind: {"cultivation": 99999} for kind in ("battle", "elite", "boss")
    }
    enemies = deepcopy(load_enemies())
    for enemy in enemies.values():
        enemy["base_stats"]["hp"] = 999999
        enemy["name"] = "后续改名"
    monkeypatch.setattr(run_api, "load_modes", lambda: modes)
    monkeypatch.setattr(run_engine, "load_enemies", lambda: enemies)
    monkeypatch.setattr(run_engine, "load_affixes", lambda: [])
    imported = await client.post("/api/saves/import", json=exported.json())
    assert imported.status_code == 201
    copied_slot = imported.json()["slot_id"]
    copied = (await client.get(f"/api/saves/{copied_slot}/run")).json()
    assert copied["run"] == started["run"]

    original_battle = await client.post(f"/api/saves/{slot}/run/choose", json={
        "revision": started["revision"], "choice": 0,
    })
    imported_battle = await client.post(f"/api/saves/{copied_slot}/run/choose", json={
        "revision": copied["revision"], "choice": 0,
    })

    assert original_battle.status_code == imported_battle.status_code == 200
    assert imported_battle.json()["run"] == original_battle.json()["run"]
    battle = imported_battle.json()["battle_result"]
    assert battle["won"] is True
    assert battle["loot"] == selected["reward"]
    assert [unit["template_id"] for unit in battle["initial_units"] if unit["side"] == "enemy"] == selected["enemies"]
    assert all(unit["name"] != "后续改名" for unit in battle["initial_units"])


async def test_legacy_route_without_new_fields_keeps_old_draws_and_can_finish(route_client):
    """缺新字段的旧局保留重复普通候选，后续仍按旧抽取推进游标，直到结束可结算。"""
    client, _ = route_client
    slot, _ = await start_route(client)
    payload = (await client.get(f"/api/saves/{slot}/export")).json()
    legacy = payload["state"]["active_run"]
    legacy["party_snapshot"].pop("route_version", None)
    legacy["party_snapshot"]["affix_pool"] = []
    mode = legacy["party_snapshot"]["mode"]
    mode["choices_per_step"] = 2
    mode["elite_chance"] = 20
    # seed=1 的旧算法前四次掷骰为 98、69、90、49，均为普通节点。
    legacy["rng_cursor"] = 4
    old_node = {
        "kind": "battle", "enemy": "battle_0", "power": mode["base_enemy_power"],
        "reward": mode["rewards"]["battle"],
    }
    legacy["choices"] = [deepcopy(old_node), deepcopy(old_node)]
    imported = await client.post("/api/saves/import", json=payload)
    assert imported.status_code == 201
    copied_slot = imported.json()["slot_id"]
    content = (await client.get(f"/api/saves/{copied_slot}/run")).json()
    assert content["run"]["party_snapshot"]["route_version"] == 1
    assert content["run"]["rng_cursor"] == 4
    assert content["run"]["choices"] == [{**old_node, "enemies": []}] * 2

    chosen = await client.post(f"/api/saves/{copied_slot}/run/choose", json={
        "revision": content["revision"], "choice": 1,
    })
    assert chosen.status_code == 200
    content = chosen.json()
    assert content["battle_result"]["won"] is True
    assert content["battle_result"]["node"]["enemies"] == []
    assert content["run"]["rng_cursor"] == 6
    assert len(content["run"]["choices"]) == 2
    assert [node["kind"] for node in content["run"]["choices"]] == ["battle", "battle"]
    assert all(node["enemies"] == [] for node in content["run"]["choices"])
    assert content["run"]["choices"][0] == content["run"]["choices"][1]
    for _ in range(19):
        if content["status"] in {"cleared", "defeated"}:
            break
        continued = await client.post(f"/api/saves/{copied_slot}/run/choose", json={
            "revision": content["revision"], "choice": 0,
        })
        assert continued.status_code == 200
        content = continued.json()
        assert content["run"]["party_snapshot"]["route_version"] == 1
    assert content["status"] in {"cleared", "defeated"}
    settled = await client.post(f"/api/saves/{copied_slot}/run/settle", json={
        "revision": content["revision"],
    })
    assert settled.status_code == 200
    assert settled.json()["state"]["active_run"] is None
