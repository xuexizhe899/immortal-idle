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


async def test_catalog_exposes_actual_battle_rules_and_skills(game_client):
    client, _ = game_client
    response = await client.get("/api/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["disciples"]["guanyu"]["asset_id"] == load_disciples()["guanyu"]["asset_id"]
    assert catalog["affixes"]["po_jun"]["bonuses"]["damage"] > 0
    assert catalog["affixes"]["tie_bi"]["effects"][0]["value"] > 0
    assert all(skill["implemented"] for skill in catalog["skills"].values())
    assert catalog["rules"]["max_party"] == 6
    assert catalog["enemies"]["stone_guard"]["base_stats"]["hp"] > 0
    assert catalog["mode"]["node_count"] == catalog["mode"]["boss_every"] == 20
    assert catalog["rules"]["injured_can_run"] is True
    assert set(catalog["production"]["materials"]) == set(catalog["materials"])
    assert len(catalog["weapons"]) == 16
    assert catalog["weapons"]["qinglong_yanyuedao"]["template_id"] == "guanyu"
    assert catalog["recipes"]["ju_qi_dan"]["max_uses"] == 3
    assert catalog["recipes"]["hui_ling_dan"]["max_uses"] == 1
    assert catalog["recipes"]["qing_feng_jian"]["max_uses"] is None


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
        "revision": content["revision"], "recipe_id": "liao_shang_dan",
    })
    assert crafted.status_code == 200
    content = crafted.json()
    assert content["state"]["inventory"]["liao_shang_dan"] == 1
    assert content["state"]["disciples"][0]["injury_stacks"] == 1
    used = await client.post(f"/api/saves/{slot}/items/use", json={
        "revision": content["revision"], "item_id": "liao_shang_dan", "target": "guanyu",
    })
    assert used.status_code == 200
    content = used.json()
    assert content["state"]["disciples"][0]["injury_stacks"] == 0
    assert "liao_shang_dan" not in content["state"]["inventory"]
    # 首轮失败收益未必足够升级；离线产出提供另一条稳定成长途径。
    for _ in range(2):
        async with factory() as session:
            await session.execute(update(save_slots).where(save_slots.c.slot_id == slot).values(
                last_settled_at=(datetime.now(timezone.utc) - timedelta(hours=12)).isoformat(),
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
    assert battle["hp_before"] - battle["damage"] + battle["healed"] == battle["hp_after"]
    assert battle["loot"] == restored["run"]["pending_loot"]


async def test_normal_artifact_can_only_be_crafted_once(game_client):
    client, _ = game_client
    slot, content = await new_slot(client)

    first = await client.post(f"/api/saves/{slot}/craft", json={
        "revision": content["revision"], "recipe_id": "qing_feng_jian",
    })
    assert first.status_code == 200
    content = first.json()
    assert content["state"]["crafted_recipes"] == ["qing_feng_jian"]
    assert content["bonuses"]["atk"] == pytest.approx(.08)
    remaining = content["state"]["inventory"]["han_tie"]

    second = await client.post(f"/api/saves/{slot}/craft", json={
        "revision": content["revision"], "recipe_id": "qing_feng_jian",
    })
    assert second.status_code == 400
    assert "已打造" in second.json()["detail"]

    latest = (await client.get(f"/api/saves/{slot}")).json()
    assert latest["state"]["inventory"]["han_tie"] == remaining
    assert latest["state"]["bonuses"]["atk"] == pytest.approx(.08)


async def test_write_settles_old_time_before_using_pill_and_keeps_anchor(game_client):
    client, factory = game_client
    slot, content = await new_slot(client)
    content = (await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": "guanyu",
    })).json()
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
    # 新的个人 +10% 修为贡献不能倒算给过去两小时，且未上岗时不影响宗门产出。
    assert content["state"]["resources"]["cultivation"] == pytest.approx(2, abs=.01)
    assert content["production"]["cultivation"] == pytest.approx(1.0)
    used = await client.post(f"/api/saves/{slot}/items/use", json={
        "revision": content["revision"], "item_id": "hui_ling_dan", "target": "guanyu",
    })
    assert used.status_code == 200
    content = used.json()
    assert content["state"]["disciples"][0]["bonuses"]["cultivation_rate"] == pytest.approx(.1)
    assert content["state"]["bonuses"] == {}
    assigned = await client.post(f"/api/saves/{slot}/duty/assign", json={
        "revision": content["revision"], "disciple_id": "guanyu",
    })
    assert assigned.status_code == 200
    content = assigned.json()
    assert content["production"]["cultivation"] == pytest.approx(1.11)
    settled = (await client.post(f"/api/saves/{slot}/settle", json={
        "revision": content["revision"],
    })).json()
    assert settled["gained"]["cultivation"] < .01


@pytest.mark.parametrize("item_id", ["hui_ling_dan", "yang_shen_dan"])
async def test_ineffective_production_pill_keeps_saved_state_and_anchor(game_client, item_id):
    """防倾向弟子不能服用无收益生产丹，失败不落账也不吞掉离线区间。"""
    client, factory = game_client
    slot, content = await new_slot(client)
    recruited = await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": "zhangfei",
    })
    assert recruited.status_code == 200
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    async with factory() as session:
        repo = SaveRepository(session)
        state, revision = await repo.get_state(slot)
        state.inventory[item_id] = 1
        assert await repo.save_state(slot, state, revision, settled_at=old)
        saved_before = await repo.get_state(slot)

    response = await client.post(f"/api/saves/{slot}/items/use", json={
        "revision": revision + 1, "item_id": item_id, "target": "zhangfei",
    })

    assert response.status_code == 400
    assert response.json()["detail"] == "该丹药无法提升该弟子的值守产出"
    async with factory() as session:
        repo = SaveRepository(session)
        assert await repo.get_state(slot) == saved_before
        assert await repo.get_last_settled_at(slot) == old


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


async def test_weapon_craft_equip_and_unequip_require_server_conditions(game_client):
    client, factory = game_client
    slot, content = await new_slot(client)
    content = (await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": "guanyu",
    })).json()

    before = (await client.get(f"/api/saves/{slot}/weapons")).json()
    guanyu_weapon = next(item for item in before["weapons"] if item["template_id"] == "guanyu")
    assert guanyu_weapon["id"] == "qinglong_yanyuedao"
    assert "8 层" in guanyu_weapon["reason"]

    async with factory() as session:
        repo = SaveRepository(session)
        state, revision = await repo.get_state(slot)
        state.tower_floor = 8
        state.disciples[0].level = 3
        state.inventory.update({
            "han_tie": 4, "jiao_gu": 2, "xuan_jing": 1,
        })
        assert await repo.save_state(slot, state, revision)
    content = (await client.get(f"/api/saves/{slot}")).json()

    crafted = await client.post(f"/api/saves/{slot}/weapons/craft", json={
        "revision": content["revision"], "weapon_id": "qinglong_yanyuedao",
    })
    assert crafted.status_code == 200
    content = crafted.json()
    assert content["state"]["inventory"]["qinglong_yanyuedao"] == 1

    duplicate = await client.post(f"/api/saves/{slot}/weapons/craft", json={
        "revision": content["revision"], "weapon_id": "qinglong_yanyuedao",
    })
    assert duplicate.status_code == 400
    assert "已拥有" in duplicate.json()["detail"]

    equipped = await client.post(f"/api/saves/{slot}/weapons/equip", json={
        "revision": content["revision"], "weapon_id": "qinglong_yanyuedao",
        "disciple_id": "guanyu",
    })
    assert equipped.status_code == 200
    content = equipped.json()
    assert content["state"]["disciples"][0]["equipment"] == ["qinglong_yanyuedao"]
    assert "qinglong_yanyuedao" not in content["state"]["inventory"]
    preview = (await client.get(f"/api/saves/{slot}/disciples/guanyu/training")).json()
    assert preview["current"]["attack"] > 0

    stale = await client.post(f"/api/saves/{slot}/weapons/unequip", json={
        "revision": content["revision"] - 1, "disciple_id": "guanyu",
    })
    assert stale.status_code == 409

    unequipped = await client.post(f"/api/saves/{slot}/weapons/unequip", json={
        "revision": content["revision"], "disciple_id": "guanyu",
    })
    assert unequipped.status_code == 200
    content = unequipped.json()
    assert content["state"]["disciples"][0]["equipment"] == []
    assert content["state"]["inventory"]["qinglong_yanyuedao"] == 1


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
    async with factory() as session:
        repo = SaveRepository(session)
        state, revision = await repo.get_state(slot)
        state.disciples[0].level = 3
        assert await repo.save_state(slot, state, revision)
    content = (await client.get(f"/api/saves/{slot}")).json()
    content = (await client.post(f"/api/saves/{slot}/disciples/guanyu/breakthrough", json={
        "revision": content["revision"],
    })).json()
    assert content["state"]["resources"]["cultivation"] == pytest.approx(1.1)
    assert content["production"]["cultivation"] == pytest.approx(1.11)
    clock[0] += timedelta(hours=1)
    content = (await client.post(f"/api/saves/{slot}/settle", json={
        "revision": content["revision"],
    })).json()
    assert content["gained"]["cultivation"] == pytest.approx(1.11)
    assert content["state"]["resources"]["cultivation"] == pytest.approx(2.21)


async def test_training_preview_and_breakthrough_gate(game_client):
    client, factory = game_client
    slot, content = await new_slot(client)
    content = (await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": content["revision"], "template_id": "guanyu",
    })).json()

    preview = (await client.get(f"/api/saves/{slot}/disciples/guanyu/training")).json()
    assert preview["level_cap"] == 3
    assert preview["next_level"]["allowed"] is False
    assert "修为" in preview["next_level"]["reason"]
    assert preview["next_realm"]["requires_level"] == 3
    assert "需要达到 3 级" in preview["next_realm"]["reason"]
    target = preview["next_realm"]["target"]
    assert target["health"] > preview["current"]["health"]
    assert target["attack"] > preview["current"]["attack"]
    assert target["defense"] > preview["current"]["defense"]

    rejected = await client.post(f"/api/saves/{slot}/disciples/guanyu/breakthrough", json={
        "revision": content["revision"],
    })
    assert rejected.status_code == 400
    assert "需要达到 3 级" in rejected.json()["detail"]

    async with factory() as session:
        repo = SaveRepository(session)
        state, revision = await repo.get_state(slot)
        state.disciples[0].level = 3
        assert await repo.save_state(slot, state, revision)
    content = (await client.get(f"/api/saves/{slot}")).json()
    preview = (await client.get(f"/api/saves/{slot}/disciples/guanyu/training")).json()
    assert preview["next_level"]["allowed"] is False
    assert "等级上限" in preview["next_level"]["reason"]
    assert preview["next_realm"]["allowed"] is True

    done = await client.post(f"/api/saves/{slot}/disciples/guanyu/breakthrough", json={
        "revision": content["revision"],
    })
    assert done.status_code == 200
    body = done.json()
    assert body["disciple"]["realm"] == 2
    assert body["disciple"]["level"] == 3
    assert body["state"]["resources"]["reputation"] == pytest.approx(
        content["state"]["resources"]["reputation"] - 110
    )

    stale = await client.post(f"/api/saves/{slot}/disciples/guanyu/breakthrough", json={
        "revision": content["revision"],
    })
    assert stale.status_code == 409


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
        ("disciples/guanyu/breakthrough", {}),
        ("duty/assign", {"disciple_id": "guanyu"}),
    ):
        response = await client.post(f"/api/saves/{slot}/{route}", json={
            "revision": revision + 1, **payload,
        })
        assert response.status_code == 400
        assert "出征" in response.json()["detail"]
