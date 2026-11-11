"""以临时数据库验证首轮闭环、刷新恢复、版本防重与结算锚点。"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import update

from app.config_loader import load_disciples
from app.api import state as state_api
from app.db import create_engine, create_session_factory
from app.main import app
from app.models.save import GameState
from app.repositories.saves import SaveRepository
from app.repositories.tables import metadata, save_slots


@pytest_asyncio.fixture
async def game_client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.domain.run_engine.secrets.randbits", lambda bits: 1)
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'game.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = create_session_factory(engine)
    app.state.session_factory = factory
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        yield client, factory
    await engine.dispose()


async def new_slot(client):
    response = await client.post("/api/saves", json={"name": "初入仙途"})
    assert response.status_code == 201
    slot = response.json()["slot_id"]
    content = (await client.get(f"/api/saves/{slot}")).json()
    return slot, content


async def test_catalog_exposes_actual_rules_and_skills_are_codex_only(game_client):
    client, _ = game_client
    response = await client.get("/api/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["disciples"]["guanyu"]["asset_id"] == load_disciples()["guanyu"]["asset_id"]
    assert catalog["affixes"]["po_jun"]["effects"][0]["value"] > 0
    assert all(not skill["implemented"] for skill in catalog["skills"].values())
    assert catalog["mode"]["node_count"] == catalog["mode"]["boss_every"] == 20
    assert catalog["rules"]["injured_can_run"] is True
    assert set(catalog["production"]["materials"]) == set(catalog["materials"])


async def test_new_slot_can_recruit_run_fail_craft_and_run_again(game_client):
    client, factory = game_client
    slot, content = await new_slot(client)
    assert content["state"]["resources"]["reputation"] == 500
    assert content["state"]["resources"]["stamina"] == 3
    # 单人出征会自然遇到极限并失败，验证失败后的恢复循环。
    recruited = await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": "guanyu",
    })
    assert recruited.status_code == 200
    content = recruited.json()
    started = await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": content["revision"], "party": ["guanyu"],
    })
    assert started.status_code == 200
    content = started.json()
    for _ in range(45):
        if content["status"] in {"defeated", "cleared"}:
            break
        route = "affix" if content["status"] == "choosing_affix" else "choose"
        decision = (
            {"affix_id": content["run"]["affix_options"][0]}
            if route == "affix" else {"choice": 0}
        )
        response = await client.post(f"/api/saves/{slot}/run/{route}", json={
            "revision": content["revision"], **decision,
        })
        assert response.status_code == 200
        content = response.json()
    assert content["status"] == "defeated"
    finished = await client.post(f"/api/saves/{slot}/run/settle", json={
        "revision": content["revision"],
    })
    assert finished.status_code == 200
    content = finished.json()
    assert content["state"]["disciples"][0]["injury_stacks"] == 1
    assert content["loot"]["reputation"] > 0
    assert "reputation" not in content["state"]["inventory"]
    crafted = await client.post(f"/api/saves/{slot}/craft", json={
        "revision": content["revision"], "recipe_id": "liao_shang_dan", "target": "guanyu",
    })
    assert crafted.status_code == 200
    content = crafted.json()
    assert content["state"]["disciples"][0]["injury_stacks"] == 0
    # 首轮失败收益未必足够升级；离线产出提供另一条稳定成长途径。
    async with factory() as session:
        await session.execute(update(save_slots).where(save_slots.c.slot_id == slot).values(
            last_settled_at=(datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
        ))
        await session.commit()
    content = (await client.post(f"/api/saves/{slot}/settle", json={
        "revision": content["revision"],
    })).json()
    upgraded = await client.post(f"/api/saves/{slot}/disciples/guanyu/upgrade", json={
        "revision": content["revision"],
    })
    assert upgraded.status_code == 200
    content = upgraded.json()
    assert content["disciple"]["level"] == 2
    assert (await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": content["revision"], "party": ["guanyu"],
    })).status_code == 200


async def test_repeat_command_is_rejected_and_refresh_preserves_battle(game_client):
    client, _ = game_client
    slot, content = await new_slot(client)
    content = (await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": "guanyu",
    })).json()
    content = (await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": content["revision"], "party": ["guanyu"],
    })).json()
    decision = {"revision": content["revision"], "choice": 0}
    first = await client.post(f"/api/saves/{slot}/run/choose", json=decision)
    assert first.status_code == 200
    content = first.json()
    assert (await client.post(f"/api/saves/{slot}/run/choose", json=decision)).status_code == 409
    restored = (await client.get(f"/api/saves/{slot}/run")).json()
    assert restored["revision"] == content["revision"]
    assert len(restored["run"]["nodes"]) == 1
    assert restored["battle_result"] == content["battle_result"]
    battle = restored["battle_result"]
    assert battle["hp_before"] - battle["damage"] == battle["hp_after"]
    assert battle["loot"] == restored["run"]["pending_loot"]


async def test_write_settles_old_time_before_crafting_and_keeps_anchor(game_client):
    client, factory = game_client
    slot, content = await new_slot(client)
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    async with factory() as session:
        await session.execute(update(save_slots).where(save_slots.c.slot_id == slot).values(
            last_settled_at=old.isoformat(),
        ))
        await session.commit()
    crafted = await client.post(f"/api/saves/{slot}/craft", json={
        "revision": content["revision"], "recipe_id": "hui_ling_dan",
    })
    assert crafted.status_code == 200
    content = crafted.json()
    # 新的 +10% 修为速率不能倒算给过去两小时。
    assert content["state"]["resources"]["cultivation"] == pytest.approx(2, abs=.01)
    assert content["production"]["cultivation"] == pytest.approx(1.1)
    settled = (await client.post(f"/api/saves/{slot}/settle", json={
        "revision": content["revision"],
    })).json()
    assert settled["gained"]["cultivation"] < .01


async def test_legacy_save_import_does_not_receive_starter_grant(game_client):
    client, _ = game_client
    imported = await client.post("/api/saves/import", json={
        "name": "旧档", "schema_version": 1, "state": GameState().model_dump(mode="json"),
    })
    assert imported.status_code == 201
    state = (await client.get(f"/api/saves/{imported.json()['slot_id']}")).json()["state"]
    assert state["resources"]["reputation"] == 0
    assert state["resources"]["stamina"] == 0
    assert state["inventory"] == {}


async def test_duty_and_run_are_mutually_exclusive_with_snapshot_rates(game_client):
    client, _ = game_client
    slot, content = await new_slot(client)
    template_id = next(key for key, value in load_disciples().items() if value["lean"] == "craft")
    content = (await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": template_id,
    })).json()
    content = (await client.post(f"/api/saves/{slot}/duty/assign", json={
        "revision": content["revision"], "disciple_id": template_id,
    })).json()
    assert content["production"]["materials"]["ling_cao"] > .5
    rejected = await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": content["revision"], "party": [template_id],
    })
    assert rejected.status_code == 400
    assert "值守" in rejected.json()["detail"]


async def test_repository_write_without_settle_preserves_elapsed_anchor(game_client):
    _, factory = game_client
    async with factory() as session:
        repo = SaveRepository(session)
        slot = await repo.create_slot("锚点")
        before = await repo.get_last_settled_at(slot)
        state, revision = await repo.get_state(slot)
        state.resources.spirit_stone = 10
        assert await repo.save_state(slot, state, revision)
        assert await repo.get_last_settled_at(slot) == before


async def test_duty_realm_upgrade_settles_old_rate_then_records_new_rate(game_client, monkeypatch):
    client, factory = game_client
    slot, content = await new_slot(client)
    clock = [datetime.now(timezone.utc)]

    class ClockDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    monkeypatch.setattr(state_api, "datetime", ClockDateTime)
    async with factory() as session:
        await session.execute(update(save_slots).where(save_slots.c.slot_id == slot).values(
            last_settled_at=clock[0].isoformat(),
        ))
        await session.commit()
    content = (await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": "guanyu",
    })).json()
    content = (await client.post(f"/api/saves/{slot}/duty/assign", json={
        "revision": content["revision"], "disciple_id": "guanyu",
    })).json()
    assert content["production"]["cultivation"] == pytest.approx(1.1)
    clock[0] += timedelta(hours=1)
    content = (await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": "guanyu",
    })).json()
    assert content["state"]["resources"]["cultivation"] == pytest.approx(1.1)
    assert content["production"]["cultivation"] == pytest.approx(1.11)
    clock[0] += timedelta(hours=1)
    content = (await client.post(f"/api/saves/{slot}/settle", json={
        "revision": content["revision"],
    })).json()
    assert content["gained"]["cultivation"] == pytest.approx(1.11)
    assert content["state"]["resources"]["cultivation"] == pytest.approx(2.21)


async def test_clock_rollback_does_not_move_anchor_or_shorten_new_injury(game_client):
    client, factory = game_client
    slot, content = await new_slot(client)
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    async with factory() as session:
        await session.execute(update(save_slots).where(save_slots.c.slot_id == slot).values(
            last_settled_at=future.isoformat(),
        ))
        await session.commit()
    content = (await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": "guanyu",
    })).json()
    content = (await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": content["revision"], "party": ["guanyu"],
    })).json()
    assert datetime.fromisoformat(content["run"]["started_at"]) == future
    # 模拟已失败待结算的旧档，不让时钟回退缩短新伤势。
    async with factory() as session:
        repo = SaveRepository(session)
        state, revision = await repo.get_state(slot)
        state.active_run.hp = 0
        assert await repo.save_state(slot, state, revision)
    finished = await client.post(f"/api/saves/{slot}/run/settle", json={
        "revision": revision + 1,
    })
    assert finished.status_code == 200
    content = finished.json()
    assert datetime.fromisoformat(content["state"]["disciples"][0]["injured_until"]) == (
        future + timedelta(hours=4)
    )
    async with factory() as session:
        assert await SaveRepository(session).get_last_settled_at(slot) == future


async def test_active_party_cannot_upgrade_recruit_or_assign_when_old_busy_flag_missing(game_client):
    client, factory = game_client
    slot, content = await new_slot(client)
    content = (await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": "guanyu",
    })).json()
    content = (await client.post(f"/api/saves/{slot}/run/start", json={
        "revision": content["revision"], "party": ["guanyu"],
    })).json()
    async with factory() as session:
        repo = SaveRepository(session)
        state, revision = await repo.get_state(slot)
        state.disciples[0].busy = False
        state.resources.cultivation = state.resources.spirit_stone = 100
        assert await repo.save_state(slot, state, revision)
    for route, payload in (
        ("disciples/guanyu/upgrade", {}),
        ("recruit", {"template_id": "guanyu"}),
        ("duty/assign", {"disciple_id": "guanyu"}),
    ):
        response = await client.post(f"/api/saves/{slot}/{route}", json={
            "revision": revision + 1, **payload,
        })
        assert response.status_code == 400
        assert "出征" in response.json()["detail"]
