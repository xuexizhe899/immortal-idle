"""永久成长：修为与灵石换取弟子等级，境界也参与战力。"""

from app.models.save import DiscipleState, GameState, Resources

LEVEL_GROWTH = 0.10
REALM_GROWTH = 0.05
UPGRADE_CULTIVATION_BASE = 20.0
UPGRADE_SPIRIT_STONE_BASE = 10.0


def new_game_state() -> GameState:
    """仅新建存档发入门资粮，读档和导入不会补发。"""
    return GameState(
        resources=Resources(stamina=3.0, reputation=500.0),
        inventory={
            "ling_cao": 5, "yun_mu": 3, "han_tie": 4,
            "jiao_gu": 2, "xuan_jing": 2, "jiu_ye": 1,
        },
    )


def upgrade_cost(disciple: DiscipleState) -> dict[str, float]:
    return {
        "cultivation": UPGRADE_CULTIVATION_BASE * disciple.level,
        "spirit_stone": UPGRADE_SPIRIT_STONE_BASE * disciple.level,
    }


def is_on_run(state: GameState, disciple: DiscipleState) -> bool:
    """active_run 的队伍身份也作校验，兼容旧档漏掉 busy 的情况。"""
    return disciple.busy or (
        state.active_run is not None and disciple.id in state.active_run.party
    )


def upgrade(state: GameState, disciple_id: str) -> tuple[dict[str, float], str | None]:
    disciple = next((d for d in state.disciples if d.id == disciple_id), None)
    if disciple is None:
        return {}, "弟子不存在"
    if is_on_run(state, disciple):
        return {}, "出征中的弟子暂不可升级"
    costs = upgrade_cost(disciple)
    for key, amount in costs.items():
        if getattr(state.resources, key) < amount:
            return costs, "修为或灵石不足"
    for key, amount in costs.items():
        setattr(state.resources, key, getattr(state.resources, key) - amount)
    disciple.level += 1
    return costs, None
