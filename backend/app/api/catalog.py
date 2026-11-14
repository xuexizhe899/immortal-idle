"""展示目录：只暴露配置里真实存在的信息与已实现规则。"""

from fastapi import APIRouter

from app.config_loader import (
    load_affixes, load_bonds, load_city, load_disciples,
    load_materials, load_modes, load_recipes, load_skills, load_enemies, load_weapons,
)
from app.domain.duty import MAX_DUTY_SLOTS
from app.domain.injuries import ATTACK_PENALTY_PER_STACK, HOURS_PER_STACK, MAX_INJURY_STACKS
from app.domain.progression import (
    LEVEL_GROWTH, REALM_GROWTH, UPGRADE_CULTIVATION_BASE, UPGRADE_SPIRIT_STONE_BASE,
)
from app.domain.run_engine import MAX_PARTY
from app.domain.settle import (
    BASE_CULTIVATION_PER_HOUR, BASE_MATERIALS_PER_HOUR,
    BASE_SPIRIT_STONE_PER_HOUR, BASE_STAMINA_PER_HOUR, IDLE_CAP_HOURS,
)
from app.models.api import CatalogResponse

router = APIRouter(tags=["catalog"])
GROUP_NAMES = {"fengrui": "锋锐", "jianshou": "坚守", "qimou": "奇谋"}


@router.get("/catalog", response_model=CatalogResponse)
async def catalog() -> CatalogResponse:
    bonds = load_bonds()
    modes = load_modes()
    return CatalogResponse(
        disciples=load_disciples(),
        affixes={
            item["id"]: {**item, "group_name": GROUP_NAMES.get(item["group"], item["group"])}
            for item in load_affixes()
        },
        recipes=load_recipes(),
        weapons={
            key: {
                "name": item["name"], "template_id": item["template_id"],
                "stats": item["stats"], "inputs": item["inputs"],
                "unlock_floor": item["unlock"]["floor"],
                "unlock_level": item["unlock"]["level"],
            }
            for key, item in load_weapons().items()
        },
        materials={key: item["name"] for key, item in load_materials().items()},
        bonds={
            key: {**item, "requires": item.get("requires", len(item["members"]))}
            for key, item in bonds.items()
        },
        skills={key: {**item, "implemented": True} for key, item in load_skills().items()},
        enemies=load_enemies(),
        mode=modes["tower"],
        modes={key: value for key, value in modes.items() if value.get("enabled")},
        rules={
            "max_party": MAX_PARTY, "max_duty": MAX_DUTY_SLOTS,
            "idle_cap_hours": IDLE_CAP_HOURS,
            "injury_attack_penalty": ATTACK_PENALTY_PER_STACK,
            "injury_hours_per_stack": HOURS_PER_STACK,
            "max_injury_stacks": MAX_INJURY_STACKS,
            "level_growth": LEVEL_GROWTH, "realm_growth": REALM_GROWTH,
            "upgrade_cultivation_base": UPGRADE_CULTIVATION_BASE,
            "upgrade_spirit_stone_base": UPGRADE_SPIRIT_STONE_BASE,
        },
        production={
            "cultivation": BASE_CULTIVATION_PER_HOUR,
            "spirit_stone": BASE_SPIRIT_STONE_PER_HOUR,
            "stamina": BASE_STAMINA_PER_HOUR,
            "materials": BASE_MATERIALS_PER_HOUR,
        },
        city=load_city(),
    )
