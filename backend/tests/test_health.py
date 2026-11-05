from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["service"] == "xiuxian-idle"
    assert body["version"] == "0.1.0"


def test_openapi_exposes_health_contract() -> None:
    schema = app.openapi()
    assert "/api/health" in schema["paths"]
    components = schema["components"]["schemas"]
    assert "HealthResponse" in components
    assert set(components["HealthResponse"]["properties"]) == {"ok", "service", "version"}
