from fastapi.testclient import TestClient

import standalone_api


client = TestClient(standalone_api.app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"message": "I'm alive!"}


def test_workshop_routes_registered_without_pro():
    paths = {route.path for route in standalone_api.app.routes}

    for prefix in (
        "/analyzer-compare",
        "/sov",
        "/sec",
        "/pipelines",
        "/labeled-analyzer",
    ):
        assert any(path.startswith(prefix) for path in paths)
    assert not any(path.startswith("/pro") for path in paths)


def test_pro_endpoint_is_not_found():
    response = client.get("/pro/healthcheck")

    assert response.status_code == 404