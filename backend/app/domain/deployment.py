"""本宗值守、外宗驻守与出征之间的人员调度。"""

from datetime import datetime

from app.models.save import DutySlot, GameState


def detach_for_run(state: GameState, party: list[str]) -> dict[str, str]:
    """出发校验通过后离岗，并保留每名随行弟子的原岗位。"""
    selected = set(party)
    posts = {slot.disciple_id: "home" for slot in state.duty_slots if slot.disciple_id in selected}
    state.duty_slots = [slot for slot in state.duty_slots if slot.disciple_id not in selected]
    for sect in state.sects:
        for slot in sect.garrison:
            if slot.disciple_id in selected:
                posts[slot.disciple_id] = sect.id
        sect.garrison = [slot for slot in sect.garrison if slot.disciple_id not in selected]
    return posts


def restore_after_run(state: GameState, return_posts: dict[str, str], now: datetime) -> list[str]:
    """结算后回原岗位；已被占满或另有安排时，不挤走现任弟子。"""
    by_id = {disciple.id: disciple for disciple in state.disciples}
    assigned = {slot.disciple_id for slot in state.duty_slots}
    assigned.update(slot.disciple_id for sect in state.sects for slot in sect.garrison)
    missed = []
    for disciple_id, post in return_posts.items():
        disciple = by_id.get(disciple_id)
        if disciple is None or disciple.busy or disciple_id in assigned:
            missed.append(disciple_id)
            continue
        sect = next((item for item in state.sects if item.id == post and item.conquered), None)
        slots = state.duty_slots if post == "home" else sect.garrison if sect else None
        capacity = 6 if post == "home" else 3
        if slots is None or len(slots) >= capacity:
            missed.append(disciple_id)
            continue
        slots.append(DutySlot(disciple_id=disciple_id, assigned_at=now))
        assigned.add(disciple_id)
    return missed


def assign_garrison(state: GameState, sect_id: str, disciple_id: str, now: datetime) -> str | None:
    """目标岗位可用后才转岗，拒绝出征者同时产生驻守收益。"""
    sect = next((item for item in state.sects if item.id == sect_id), None)
    if sect is None or not sect.conquered:
        return "请先攻克该宗门"
    disciple = next((item for item in state.disciples if item.id == disciple_id), None)
    if disciple is None:
        return "弟子不存在"
    if disciple.busy or (state.active_run and disciple_id in state.active_run.party):
        return "该弟子正在出征"
    if any(slot.disciple_id == disciple_id for slot in sect.garrison):
        return "该弟子已在此宗门驻守"
    if len(sect.garrison) >= 3:
        return "该宗门最多驻守三名弟子"
    detach_for_run(state, [disciple_id])
    sect.garrison.append(DutySlot(disciple_id=disciple_id, assigned_at=now))
    return None


def unassign_garrison(state: GameState, sect_id: str, disciple_id: str) -> str | None:
    sect = next((item for item in state.sects if item.id == sect_id), None)
    if sect is None or not any(slot.disciple_id == disciple_id for slot in sect.garrison):
        return "该弟子不在此宗门驻守"
    sect.garrison = [slot for slot in sect.garrison if slot.disciple_id != disciple_id]
    return None
