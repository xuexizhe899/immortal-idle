"""静态目录接口：前端展示用的名称映射，避免前端硬编码中文名。"""

from fastapi import APIRouter

from app.config_loader import load_affixes, load_disciples, load_recipes

router = APIRouter(tags=["catalog"])


@router.get("/catalog")
async def catalog() -> dict:
    """返回弟子、词条、配方的展示信息。"""
    return {
        "disciples": {
            key: {
                "name": item["name"],
                "title": item.get("title", ""),
                "lean": item["lean"],
                "rarity": item["rarity"],
            }
            for key, item in load_disciples().items()
        },
        "affixes": {
            item["id"]: {"name": item["name"], "group": item["group"]}
            for item in load_affixes()
        },
        "recipes": {
            key: {"name": item["name"], "kind": item["kind"]}
            for key, item in load_recipes().items()
        },
    }
