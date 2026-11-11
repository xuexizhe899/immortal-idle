"""响应 always 包含的默认字段必须反映在生成契约中。"""

from app.main import app
from app.models.save import GameState


def test_serialization_requires_defaults_without_breaking_legacy_input():
    legacy = GameState.model_validate({})
    assert legacy.duty_slots == []
    assert legacy.active_run is None
    input_schema = GameState.model_json_schema(mode="validation")
    output_schema = GameState.model_json_schema(mode="serialization")
    assert "duty_slots" not in input_schema.get("required", [])
    assert set(output_schema["required"]) == set(output_schema["properties"])
    active_run = output_schema["$defs"]["ActiveRun"]
    assert {"party", "nodes", "choices", "affixes", "last_battle"} <= set(active_run["required"])
    disciple = output_schema["$defs"]["DiscipleState"]
    assert {"level", "realm", "injury_stacks", "stats"} <= set(disciple["required"])


def test_openapi_uses_output_state_and_complete_nested_catalog():
    schemas = app.openapi()["components"]["schemas"]
    state_ref = schemas["GameSnapshot"]["properties"]["state"]["$ref"]
    output_state = schemas[state_ref.rsplit("/", 1)[-1]]
    assert {"disciples", "duty_slots", "unlocks", "resources"} <= set(output_state["required"])
    assert {"effects", "special"} <= set(schemas["RecipeCatalog"]["required"])
    assert "injury_recovery_multiplier" in schemas["ProductionCatalog"]["required"]
