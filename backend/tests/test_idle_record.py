"""挂机累计记录使用后端时间并与收益、锚点及 revision 一起持久化。"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.api import saves as saves_api
from app.api import state as state_api
from app.db import create_engine, create_session_factory
from app.domain.settle import settle
from app.main import app
from app.models.save import DutyEvent, GameState
from app.repositories import saves as saves_repo
from app.repositories.saves import SaveRepository
from app.repositories.tables import metadata

T0 = datetime(2026, 11, 19, 0, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def idle_client(tmp_path, monkeypatch):
    clock = [T0]

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    monkeypatch.setattr(state_api, "datetime", FrozenDateTime)
    monkeypatch.setattr(saves_api, "datetime", FrozenDateTime)
    monkeypatch.setattr(saves_repo, "utcnow", lambda: clock[0])
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'idle-record.db').as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    factory = create_session_factory(engine)
    monkeypatch.setattr(app.state, "session_factory", factory, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory, clock
    await engine.dispose()


async def new_slot(client, name="挂机记录测试"):
    response = await client.post("/api/saves", json={"name": name})
    assert response.status_code == 201
    slot = response.json()["slot_id"]
    content = await client.get(f"/api/saves/{slot}")
    assert content.status_code == 200
    return slot, content.json()


async def stored(factory, slot):
    async with factory() as session:
        repo = SaveRepository(session)
        state, revision = await repo.get_state(slot)
        return state.model_dump(mode="json"), revision, await repo.get_last_settled_at(slot)


async def test_online_command_and_same_time_collection_keep_offline_record_after_reload(idle_client):
    client, factory, clock = idle_client
    slot, initial = await new_slot(client)
    clock[0] += timedelta(hours=2)
    recruited = await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": initial["revision"], "template_id": "guanyu",
    })
    assert recruited.status_code == 200
    content = recruited.json()
    record = content["state"]["idle_record"]
    assert record["elapsed_hours"] == 2
    assert record["cultivation"] == 2
    assert record["spirit_stone"] == 1
    assert record["stamina"] == 1
    assert record["materials"] == {
        key: count - initial["state"]["inventory"].get(key, 0)
        for key, count in content["state"]["inventory"].items()
        if count > initial["state"]["inventory"].get(key, 0)
    }
    assert datetime.fromisoformat(record["started_at"]) == T0
    assert datetime.fromisoformat(record["updated_at"]) == clock[0]
    before_resources = content["state"]["resources"]
    before_inventory = content["state"]["inventory"]

    settled = await client.post(f"/api/saves/{slot}/settle", json={"revision": content["revision"]})
    assert settled.status_code == 200
    result = settled.json()
    assert result["elapsed_hours"] == 0
    assert result["state"]["idle_record"] == record
    assert result["state"]["resources"] == before_resources
    assert result["state"]["inventory"] == before_inventory
    refreshed = await client.get(f"/api/saves/{slot}")
    assert refreshed.status_code == 200
    assert refreshed.json()["state"]["idle_record"] == record
    persisted, revision, anchor = await stored(factory, slot)
    assert persisted["idle_record"] == record
    assert persisted["resources"] == before_resources
    assert persisted["inventory"] == before_inventory
    assert revision == result["revision"]
    assert anchor == clock[0]


async def test_new_and_legacy_slots_default_empty_and_accumulate_independently(idle_client):
    client, factory, clock = idle_client
    first, first_content = await new_slot(client, "第一宗门")
    legacy = GameState().model_dump(mode="json")
    legacy.pop("idle_record", None)
    imported = await client.post("/api/saves/import", json={"name": "旧档", "schema_version": 1, "state": legacy})
    assert imported.status_code == 201
    second = imported.json()["slot_id"]
    second_content = (await client.get(f"/api/saves/{second}")).json()
    empty = {
        "started_at": None, "updated_at": None, "elapsed_hours": 0, "dropped_hours": 0,
        "cultivation": 0, "spirit_stone": 0, "stamina": 0, "materials": {},
    }
    assert first_content["state"]["idle_record"] == empty
    assert second_content["state"]["idle_record"] == empty
    clock[0] += timedelta(hours=1)
    first_result = await client.post(f"/api/saves/{first}/settle", json={"revision": first_content["revision"]})
    assert first_result.status_code == 200
    first_record = first_result.json()["state"]["idle_record"]
    assert first_record["elapsed_hours"] == 1
    assert (await client.get(f"/api/saves/{second}")).json()["state"]["idle_record"] == empty
    clock[0] += timedelta(hours=1)
    second_result = await client.post(f"/api/saves/{second}/settle", json={"revision": second_content["revision"]})
    assert second_result.status_code == 200
    second_record = second_result.json()["state"]["idle_record"]
    assert second_record["elapsed_hours"] == 2
    assert second_result.json()["state"]["resources"]["cultivation"] == 2
    assert (await client.get(f"/api/saves/{first}")).json()["state"]["idle_record"] == first_record
    assert (await stored(factory, first))[0]["idle_record"] == first_record
    assert (await stored(factory, second))[0]["idle_record"] == second_record


def test_record_accumulates_across_online_intervals_and_caps_only_each_offline_gap():
    state = GameState()
    previous = T0
    for hours in (8, 16, 36):
        now = T0 + timedelta(hours=hours)
        settle(state, previous, now)
        previous = now
    record = state.idle_record
    assert record.elapsed_hours == 28
    assert record.dropped_hours == 8
    assert record.started_at == T0
    assert record.updated_at == previous
    assert record.cultivation == state.resources.cultivation == 28
    assert record.spirit_stone == state.resources.spirit_stone == 14
    assert record.stamina == state.resources.stamina == 14
    assert record.materials == state.inventory
    restored = GameState.model_validate_json(state.model_dump_json())
    assert restored.idle_record == record

    capped = GameState()
    settle(capped, T0, T0 + timedelta(hours=20))
    assert capped.idle_record.started_at == T0
    assert capped.idle_record.elapsed_hours == 12
    assert capped.idle_record.dropped_hours == 8


def test_split_record_keeps_unrounded_resource_totals_and_actual_integer_materials():
    whole = GameState(duty_events=[DutyEvent(at=T0, rates={
        "cultivation_rate": .123456789, "material_ling_cao_flat": .07,
    })])
    split = whole.model_copy(deep=True)
    settle(whole, T0, T0 + timedelta(hours=2))
    for minute in range(120):
        settle(split, T0 + timedelta(minutes=minute), T0 + timedelta(minutes=minute + 1))
    for key in ("elapsed_hours", "dropped_hours", "cultivation", "spirit_stone", "stamina"):
        assert getattr(split.idle_record, key) == pytest.approx(getattr(whole.idle_record, key), abs=1e-12)
    assert split.idle_record.cultivation == pytest.approx(2.246913578)
    assert split.idle_record.materials == whole.idle_record.materials == split.inventory == whole.inventory
    assert split.material_remainders == pytest.approx(whole.material_remainders)
    assert split.idle_record.started_at == whole.idle_record.started_at == T0
    assert split.idle_record.updated_at == whole.idle_record.updated_at == T0 + timedelta(hours=2)


async def test_rejected_command_and_stale_or_competing_cas_do_not_persist_record(idle_client):
    client, factory, clock = idle_client
    slot, initial = await new_slot(client)
    before = await stored(factory, slot)
    clock[0] += timedelta(hours=2)
    rejected = await client.post(f"/api/saves/{slot}/recruit", json={
        "revision": initial["revision"], "template_id": "missing_disciple",
    })
    assert rejected.status_code == 400
    assert await stored(factory, slot) == before
    stale = await client.post(f"/api/saves/{slot}/settle", json={"revision": initial["revision"] + 1})
    assert stale.status_code == 409
    assert await stored(factory, slot) == before

    # 两个命令均已在内存补算同一段时间，只有 CAS 胜出的记录可以与资源一起落盘。
    async with factory() as first_session, factory() as second_session:
        first_repo, second_repo = SaveRepository(first_session), SaveRepository(second_session)
        first = await state_api.prepare_mutation(slot, first_repo, initial["revision"])
        second = await state_api.prepare_mutation(slot, second_repo, initial["revision"])
        await state_api.commit_mutation(slot, first, first_repo)
        after_first = await stored(factory, slot)
        with pytest.raises(HTTPException) as failure:
            await state_api.commit_mutation(slot, second, second_repo)
        assert failure.value.status_code == 409
    assert await stored(factory, slot) == after_first
    state, revision, anchor = after_first
    assert state["idle_record"]["elapsed_hours"] == 2
    assert state["resources"]["cultivation"] == initial["state"]["resources"]["cultivation"] + 2
    assert revision == initial["revision"] + 1
    assert anchor == clock[0]


async def test_same_time_and_clock_rollback_preserve_record_and_forward_only_anchor(idle_client):
    client, factory, clock = idle_client
    slot, initial = await new_slot(client)
    clock[0] += timedelta(hours=2)
    first = (await client.post(f"/api/saves/{slot}/settle", json={"revision": initial["revision"]})).json()
    record = deepcopy(first["state"]["idle_record"])
    resources = deepcopy(first["state"]["resources"])
    clock[0] -= timedelta(hours=1)
    backward = await client.post(f"/api/saves/{slot}/settle", json={"revision": first["revision"]})
    assert backward.status_code == 200
    content = backward.json()
    assert content["elapsed_hours"] == 0
    assert content["warnings"]
    assert content["state"]["idle_record"] == record
    assert content["state"]["resources"] == resources
    assert (await stored(factory, slot))[2] == T0 + timedelta(hours=2)
    clock[0] = T0 + timedelta(hours=3)
    forward = await client.post(f"/api/saves/{slot}/settle", json={"revision": content["revision"]})
    assert forward.status_code == 200
    content = forward.json()
    assert content["elapsed_hours"] == 1
    assert content["state"]["idle_record"]["elapsed_hours"] == 3
    assert content["state"]["idle_record"]["cultivation"] == 3
    before_same_time = await stored(factory, slot)
    repeated = await client.post(f"/api/saves/{slot}/settle", json={"revision": content["revision"]})
    assert repeated.status_code == 200
    assert repeated.json()["state"]["idle_record"] == content["state"]["idle_record"]
    assert repeated.json()["state"]["resources"] == content["state"]["resources"]
    persisted, revision, anchor = await stored(factory, slot)
    assert persisted == before_same_time[0]
    assert revision == before_same_time[1] + 1
    assert anchor == before_same_time[2] == T0 + timedelta(hours=3)
