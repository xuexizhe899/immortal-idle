"""世界图层、片区里程碑、有限迎击与飞升；出发定义可完整固化进战斗快照。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.models.world import (
    AreaView, AscensionView, InvasionView, RegionView, WorldNodeView, WorldView,
)

if TYPE_CHECKING:
    from app.models.save import GameState


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def ensure_world(state: GameState, now: datetime, config: dict) -> bool:
    """为已开放地区补齐敌情；达到上限停止蓄积，时钟回拨不退锚点。"""
    changed = False
    now = _utc(now)
    world = state.world
    invasion = config["invasion"]
    cap = invasion["pending_cap"]
    period = timedelta(hours=invasion["hours_per_wave"])
    for region_id in world.unlocked_regions:
        key = str(region_id)
        for mapping, default in (
            (world.unlocked_areas, 1),
            (world.pending_invasions, invasion["initial_pending"]),
            (world.invasion_waves, 1),
        ):
            if key not in mapping:
                mapping[key] = default
                changed = True
        anchor = world.last_invasion_at.get(key)
        if anchor is None:
            world.last_invasion_at[key] = now
            changed = True
            continue
        anchor = _utc(anchor)
        if now <= anchor:
            continue
        pending = world.pending_invasions[key]
        elapsed = (now - anchor) // period
        if pending == cap:
            continue
        if pending > cap or pending + elapsed >= cap:
            world.pending_invasions[key] = cap
            world.last_invasion_at[key] = now
            changed = True
        elif elapsed:
            world.pending_invasions[key] += elapsed
            world.last_invasion_at[key] = anchor + period * elapsed
            changed = True
    key = str(world.current_region)
    if key not in world.tower_records:
        world.tower_records[key] = dict(state.tower_tiers)
        changed = True
    return changed


def _region(config: dict, region_id: int) -> dict | None:
    return next((item for item in config["regions"] if item["id"] == region_id), None)


def _nodes(state: GameState, region: dict, config: dict) -> list[WorldNodeView]:
    world = state.world
    region_id = region["id"]
    opened = world.unlocked_areas.get(str(region_id), 1)
    region_reason = "请先使用升仙令解锁此地区" if region_id not in world.unlocked_regions else ""
    nodes = []
    for area in region["areas"]:
        area_id = area["id"]
        x = 18 + (area_id - 1) * 32
        reason = region_reason or ("请先击败前一片区的守关首领" if area_id > opened else "")
        scale = region["enemy_scale"] * area["scale"]
        for index in range(3):
            number = (area_id - 1) * 3 + index + 1
            sect_id = f"sect_{number}" if region_id == 1 else f"r{region_id}:sect_{number}"
            sect = next((item for item in state.sects if item.id == sect_id), None)
            sect_reason = reason or ("请先提升宗门大殿，开放此宗门" if sect is None else "")
            nodes.append(WorldNodeView(
                id=f"r{region_id}:sect:{number}", kind="sect", name=sect.name if sect else f"待开放宗门·{number}",
                description="征讨获胜后可驻守产材；已攻克宗门可反复论道。", region_id=region_id,
                area=area_id, x=x + (index - 1) * 8, y=19, sect_id=sect_id,
                locked=bool(sect_reason), reason=sect_reason, cleared=bool(sect and sect.conquered),
                stamina_cost=2, enemy_scale=scale, gear_tier=region["gear_tier"],
                rewards=sect.loot if sect else {},
            ))
        for index, dungeon in enumerate(area["dungeons"], 1):
            nodes.append(WorldNodeView(
                id=f"r{region_id}:dungeon:{area_id}:{index}", kind="dungeon", name=dungeon["name"],
                description=f"六段秘境，可选择敌情与机缘；失败仍保留已获战利品。{area['threat']}",
                region_id=region_id, area=area_id, x=x + (-7 if index == 1 else 7), y=41,
                locked=bool(reason), reason=reason, stamina_cost=2, enemy_scale=scale,
                enemy_ids=list(area["enemies"]), node_count=6, gear_tier=region["gear_tier"],
                gear_slot=dungeon["slot"],
            ))
        gate_id = f"r{region_id}:gate:{area_id}"
        nodes.append(WorldNodeView(
            id=gate_id, kind="gate", name=f"{area['name']}·守关", description=area["threat"],
            region_id=region_id, area=area_id, x=x, y=61, locked=bool(reason), reason=reason,
            cleared=gate_id in world.cleared_nodes, stamina_cost=1, enemy_scale=scale * area.get("gate_multiplier", 1.15),
            enemy_ids=list(area["boss"]), gear_tier=region["gear_tier"], rewards=area["first_reward"],
        ))
        invasion_id = f"r{region_id}:invasion:{area_id}"
        invasion_reason = reason or ("请先击败本片区守关首领" if gate_id not in world.cleared_nodes else "")
        if not invasion_reason and area_id > 1 and f"r{region_id}:invasion:{area_id - 1}" not in world.cleared_nodes:
            invasion_reason = "请先击退前一片区的关键入侵"
        nodes.append(WorldNodeView(
            id=invasion_id, kind="invasion", name=f"{area['name']}·关键入侵",
            description=f"首胜获得阶段奖励，重复挑战不重复领奖。{area['threat']}",
            region_id=region_id, area=area_id, x=x, y=80, locked=bool(invasion_reason),
            reason=invasion_reason, cleared=invasion_id in world.cleared_nodes,
            enemy_scale=scale * area.get("invasion_multiplier", 1.3), enemy_ids=list(area["boss"]),
            gear_tier=region["gear_tier"], rewards=area["invasion_reward"],
        ))
    wave = world.invasion_waves.get(str(region_id), 1)
    pending = world.pending_invasions.get(str(region_id), 0)
    raid_growth = min(config["invasion"]["wave_scale_cap"], 1 + (wave - 1) * config["invasion"]["wave_growth"])
    raid_scale = region["enemy_scale"] * raid_growth
    raid_rewards = {key: value * region["reward_scale"] for key, value in config["invasion"]["reward"].items()}
    nodes.append(WorldNodeView(
        id=f"r{region_id}:raid", kind="raid", name=f"普通迎击·第{wave}波",
        description="挂机积攒敌情，玩家自行选择接战；无待迎击时仍可无奖励演练。",
        region_id=region_id, area=1, x=9, y=94, locked=bool(region_reason or not pending),
        reason=region_reason or ("暂无待迎击敌情，可选择演练" if not pending else ""),
        enemy_scale=raid_scale, enemy_ids=list(config["invasion"]["enemies"]),
        gear_tier=region["gear_tier"], rewards=raid_rewards, wave=wave,
    ))
    nodes.append(WorldNodeView(
        id=f"r{region_id}:tower", kind="tower", name="问道塔",
        description="每阶二十层，地区之间分别保留塔阶纪录；请在塔中选择已开放塔阶。",
        region_id=region_id, area=1, x=91, y=94, locked=bool(region_reason), reason=region_reason,
        stamina_cost=config.get("tower_stamina_cost", 1), enemy_scale=region["enemy_scale"], node_count=20,
        gear_tier=region["gear_tier"],
    ))
    return nodes


def _ascension(state: GameState, config: dict) -> AscensionView:
    current = state.world.current_region
    target = next((item["id"] for item in config["regions"] if item["id"] > current), None)
    token = config["ascension_token"]
    held = state.inventory.get(token, 0)
    reason = ""
    if target is None:
        reason = "后续地区尚未开放，仍可培养弟子、攻宗与挑战纪录"
    elif target in state.world.unlocked_regions:
        reason = "下一地区已开放，可直接切换图层"
    else:
        region = _region(config, current)
        final_area = max(item["id"] for item in region["areas"])
        if f"r{current}:invasion:{final_area}" not in state.world.cleared_nodes:
            reason = "请先击退本地区最终关键入侵"
        elif held < 1:
            reason = "需要一枚升仙令"
        elif state.active_run is not None:
            reason = "请先结算当前出征"
    return AscensionView(target_region=target, token_id=token, held=held, can_ascend=not reason, reason=reason)


def world_view(state: GameState, config: dict) -> WorldView:
    """只投影已有事实，不推进敌情时间、不发奖励。"""
    world = state.world
    regions = []
    for region in config["regions"]:
        opened = region["id"] in world.unlocked_regions
        regions.append(RegionView(
            id=region["id"], name=region["name"], subtitle=region["subtitle"], unlocked=opened,
            selected=region["id"] == world.current_region, palette=region["palette"],
            enemy_scale=region["enemy_scale"],
            areas=[AreaView(id=area["id"], name=area["name"], description=area["description"],
                            unlocked=opened and area["id"] <= world.unlocked_areas.get(str(region["id"]), 1))
                   for area in region["areas"]],
            nodes=_nodes(state, region, config),
        ))
    invasion = config["invasion"]
    key = str(world.current_region)
    pending = world.pending_invasions.get(key, 0)
    anchor = world.last_invasion_at.get(key)
    next_at = _utc(anchor) + timedelta(hours=invasion["hours_per_wave"]) if anchor and pending < invasion["pending_cap"] else None
    current = next(item for item in regions if item.selected)
    return WorldView(
        current_region=world.current_region, regions=regions,
        invasions=InvasionView(pending=pending, cap=invasion["pending_cap"],
                              wave=world.invasion_waves.get(key, 1), hours_per_wave=invasion["hours_per_wave"],
                              next_at=next_at, critical_nodes=[item for item in current.nodes if item.kind == "invasion"]),
        ascension=_ascension(state, config),
    )


def tower_mode(state: GameState, base_mode: dict, config: dict) -> dict:
    """两种塔入口共用完整旧塔规则，只追加已公布的地区倍率与行动力成本。"""
    mode = deepcopy(base_mode)
    region = _region(config, state.world.current_region)
    mode["stamina_cost"] = config.get("tower_stamina_cost", base_mode["stamina_cost"])
    mode["gear_tier"] = region["gear_tier"]
    mode["kind_stat_multiplier"] = {
        kind: value * region["enemy_scale"] for kind, value in base_mode["kind_stat_multiplier"].items()
    }
    mode["rewards"] = {
        kind: {key: value * region["reward_scale"] for key, value in reward.items()}
        for kind, reward in base_mode["rewards"].items()
    }
    mode["defeat_floor_reward"] = {key: value * region["reward_scale"] for key, value in base_mode["defeat_floor_reward"].items()}
    return mode


def prepare_world_node(
    state: GameState, node_id: str, config: dict, practice: bool = False,
) -> tuple[dict | None, str | None]:
    """校验目标并返回独立快照；不扣行动力、不改变波次，出征入口原子处理。"""
    region = _region(config, state.world.current_region)
    node = next((item for item in _nodes(state, region, config) if item.id == node_id), None)
    if node is None:
        return None, "目标不在当前地区"
    if state.active_run is not None:
        return None, "请先结算当前出征"
    if node.locked and not (practice and node.kind == "raid" and node.region_id in state.world.unlocked_regions):
        return None, node.reason
    area = next(item for item in region["areas"] if item["id"] == node.area)
    snapshot = node.model_dump(mode="json")
    snapshot["practice"] = practice
    snapshot["claim_key"] = f"{node.id}:wave{node.wave}" if node.kind == "raid" else node.id
    snapshot["completion_rewards"] = deepcopy(node.rewards) if node.kind in {"gate", "invasion", "raid"} else {}
    snapshot["unlocks_area"] = min(node.area + 1, max(item["id"] for item in region["areas"]))
    snapshot["invasion_cap"] = config["invasion"]["pending_cap"]
    snapshot["invasion_hours_per_wave"] = config["invasion"]["hours_per_wave"]
    if node.kind == "tower":
        # 两入口先用 tower_mode 组装同一完整模式，地图节点不另造奖励和路线定义。
        snapshot["mode_overrides"] = {"stamina_cost": node.stamina_cost}
        return snapshot, None
    scale = node.enemy_scale
    single = node.kind in {"gate", "invasion", "raid"}
    battle = node.enemy_ids if single else area["enemies"]
    elite = node.enemy_ids if single else area["elite"]
    boss = node.enemy_ids if single else area["boss"]
    reward_scale = region["reward_scale"] * (1 + .35 * (node.area - 1))
    rewards = {} if single else {"cultivation": 12 * reward_scale, "spirit_stone": 6 * reward_scale,
                                "reputation": config.get("dungeon_reputation", 2) * reward_scale,
                                "lian_qi_jing_cui": 2 * region["gear_tier"]}
    snapshot["mode_overrides"] = {
        "node_count": node.node_count, "boss_every": node.node_count,
        "stamina_cost": 0 if practice else node.stamina_cost,
        "enemy_growth": 0 if single else .045,
        "encounters": {"battle": list(battle), "elite": list(elite), "boss": list(boss)},
        "encounter_variants": {},
        "kind_stat_multiplier": {"battle": scale, "elite": scale * 1.06, "boss": scale * (1 if single else 1.12)},
        "rewards": {kind: {} if practice else {key: round(value * multiplier, 2) for key, value in rewards.items()}
                    for kind, multiplier in (("battle", 1), ("elite", 1.5), ("boss", 2.5))},
        "defeat_ratio": 1.0, "defeat_floor_reward": {},
    }
    if practice:
        snapshot["completion_rewards"] = {}
    return snapshot, None


def finish_world_node(
    state: GameState, node: dict | WorldNodeView, victory: bool, now: datetime,
    config: dict, practice: bool = False,
) -> dict[str, float]:
    """胜利时推进正式事实并返回一次性奖励；奖励由统一结算入口入账。"""
    snapshot = node.model_dump(mode="json") if isinstance(node, WorldNodeView) else node
    if not victory or practice or snapshot.get("practice"):
        return {}
    world = state.world
    identity = snapshot["id"]
    kind = snapshot["kind"]
    key = str(snapshot["region_id"])
    if kind not in {"gate", "invasion", "raid"}:
        return {}
    claim_key = snapshot.get("claim_key", f"{identity}:wave{snapshot.get('wave', 0)}" if kind == "raid" else identity)
    if claim_key in world.claimed_nodes:
        return {}
    if kind == "raid":
        wave = snapshot.get("wave", 0)
        if wave != world.invasion_waves.get(key, 1) or world.pending_invasions.get(key, 0) <= 0:
            return {}
        # 只有成功消耗已快照的这一波；失败和演练不推进，也不在满仓期间偷蓄下一波。
        if world.pending_invasions[key] >= snapshot.get("invasion_cap", config["invasion"]["pending_cap"]):
            anchor = world.last_invasion_at.get(key)
            world.last_invasion_at[key] = max(_utc(anchor), _utc(now)) if anchor else _utc(now)
        world.pending_invasions[key] -= 1
        world.invasion_waves[key] = wave + 1
    else:
        if identity not in world.cleared_nodes:
            world.cleared_nodes.append(identity)
        if kind == "gate":
            world.unlocked_areas[key] = max(world.unlocked_areas.get(key, 1), snapshot.get("unlocks_area", snapshot["area"] + 1))
    world.claimed_nodes.append(claim_key)
    return deepcopy(snapshot.get("completion_rewards", snapshot.get("rewards", {})))


def travel_region(state: GameState, region_id: int, now: datetime, config: dict) -> str | None:
    """免费往返已开放图层；弟子、装备、资源及全地区驻守均原样保留。"""
    if state.active_run is not None:
        return "请先结算当前出征"
    if _region(config, region_id) is None or region_id not in state.world.unlocked_regions:
        return "此地区尚未开放"
    ensure_world(state, now, config)
    world = state.world
    world.tower_records[str(world.current_region)] = dict(state.tower_tiers)
    world.current_region = region_id
    state.tower_tiers = dict(world.tower_records.get(str(region_id), {}))
    return None


def ascend(state: GameState, now: datetime, config: dict) -> str | None:
    """最终入侵首胜后消耗一枚令牌开放下一层；重复请求不会重复扣费。"""
    view = _ascension(state, config)
    if not view.can_ascend:
        return view.reason
    state.inventory[view.token_id] -= 1
    state.world.unlocked_regions.append(view.target_region)
    return travel_region(state, view.target_region, now, config)
