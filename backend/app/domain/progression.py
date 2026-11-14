"""永久成长：修为与灵石换取弟子等级，境界决定阶段上限与值守。

等级只影响战斗；境界影响战斗、值守速率和后续等级上限。
境界 1/2/3 的等级上限为 3/6/10，突破需要达到当前上限并支付声望或使用破境丹。
"""

from app.models.save import DiscipleState, GameState, Resources

LEVEL_GROWTH = 0.10
REALM_GROWTH = 0.05
UPGRADE_CULTIVATION_BASE = 20.0
UPGRADE_SPIRIT_STONE_BASE = 10.0

# 境界 -> 当前阶段可达到的最高等级；未列出的旧档境界按 10 级处理
LEVEL_CAPS = {1: 3, 2: 6, 3: 10}
MAX_REALM = 3
MAX_LEVEL = 10
# 突破到目标境界所需解锁声望的比例；境界 3 的费用高于境界 2
REALM_UP_RATIOS = {2: 0.5, 3: 0.75}


def new_game_state() -> GameState:
    """仅新建存档发入门资粮，读档和导入不会补发。"""
    return GameState(
        resources=Resources(stamina=3.0, reputation=500.0),
        inventory={
            "ling_cao": 5, "yun_mu": 3, "han_tie": 4,
            "jiao_gu": 2, "xuan_jing": 2, "jiu_ye": 1,
            "ling_mu": 4, "qing_shi": 4, "chi_tong": 2, "yao_shou_pi": 2,
        },
    )


def level_cap(realm: int) -> int:
    """当前境界允许达到的最高等级；旧档超出设计境界时仍以 10 级为上限。"""
    return LEVEL_CAPS.get(realm, MAX_LEVEL)


def upgrade_cost(disciple: DiscipleState) -> dict[str, float]:
    return {
        "cultivation": UPGRADE_CULTIVATION_BASE * disciple.level,
        "spirit_stone": UPGRADE_SPIRIT_STONE_BASE * disciple.level,
    }


def breakthrough_cost(disciple: DiscipleState, template: dict) -> dict[str, float]:
    """突破到下一境界所需声望；已到最高境界时返回空。"""
    ratio = REALM_UP_RATIOS.get(disciple.realm + 1, 0.0)
    reputation = template.get("unlock_cost", {}).get("reputation", 0.0) * ratio
    return {"reputation": reputation} if reputation else {}


def is_on_run(state: GameState, disciple: DiscipleState) -> bool:
    """active_run 的队伍身份也作校验，兼容旧档漏掉 busy 的情况。"""
    return disciple.busy or (
        state.active_run is not None and disciple.id in state.active_run.party
    )


def can_upgrade(state: GameState, disciple: DiscipleState) -> str | None:
    """返回不能升级的原因；可升级返回 None。"""
    if is_on_run(state, disciple):
        return "出征中的弟子暂不可升级"
    cap = level_cap(disciple.realm)
    if disciple.level >= cap:
        return f"已达境界 {disciple.realm} 的等级上限 {cap}，请先突破"
    costs = upgrade_cost(disciple)
    if any(getattr(state.resources, key) < amount for key, amount in costs.items()):
        return "修为或灵石不足"
    return None


def upgrade(state: GameState, disciple_id: str) -> tuple[dict[str, float], str | None]:
    """提升一级；达到当前境界上限时拒绝，不修改资源。"""
    disciple = next((d for d in state.disciples if d.id == disciple_id), None)
    if disciple is None:
        return {}, "弟子不存在"
    costs = upgrade_cost(disciple)
    error = can_upgrade(state, disciple)
    if error:
        return costs, error
    for key, amount in costs.items():
        setattr(state.resources, key, getattr(state.resources, key) - amount)
    disciple.level += 1
    return costs, None


def can_breakthrough(
    state: GameState, disciple: DiscipleState, template: dict,
    *, pay_reputation: bool = True,
) -> tuple[dict[str, float], str | None]:
    """校验境界突破；破境丹路径传 pay_reputation=False。"""
    costs = breakthrough_cost(disciple, template)
    if is_on_run(state, disciple):
        return costs, "出征中的弟子暂不可突破"
    if disciple.realm >= MAX_REALM:
        return costs, "已达当前最高境界"
    required = LEVEL_CAPS.get(disciple.realm)
    if required is None:
        return costs, "当前境界不支持继续突破"
    if disciple.level < required:
        return costs, f"需要达到 {required} 级才能突破至境界 {disciple.realm + 1}"
    if pay_reputation and state.resources.reputation < costs.get("reputation", 0.0):
        return costs, f"声望不足（需要 {costs.get('reputation', 0.0):g}）"
    return costs, None


def breakthrough(
    state: GameState, disciple_id: str, templates: dict[str, dict],
    *, pay_reputation: bool = True,
) -> tuple[dict[str, float], str | None]:
    """突破一层境界；等级不重置，旧档超限等级保留。"""
    disciple = next((d for d in state.disciples if d.id == disciple_id), None)
    if disciple is None:
        return {}, "弟子不存在"
    template = templates.get(disciple.template_id)
    if template is None:
        return {}, "弟子模板未配置"
    costs, error = can_breakthrough(
        state, disciple, template, pay_reputation=pay_reputation,
    )
    if error:
        return costs, error
    if pay_reputation:
        state.resources.reputation -= costs.get("reputation", 0.0)
    disciple.realm += 1
    return costs, None
