from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import claims
from app.services import claims_service as service

app = FastAPI()
app.include_router(claims.router)
client = TestClient(app)


def test_folder_detail_and_original_image_do_not_need_azure(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAIMS_OUTPUT_ROOT", str(tmp_path))
    overview = client.get("/claims")
    assert overview.status_code == 200
    assert len(overview.json()["claims"]) == 6
    detail = client.get("/claims/claim-003")
    assert detail.status_code == 200
    image = next(item for item in detail.json()["files"] if item["source_type"] == "image")
    raw = client.get(f"/claims/claim-003/files/{image['id']}/raw")
    assert raw.status_code == 200
    assert raw.headers["content-type"].startswith("image/")
    assert raw.headers["x-content-type-options"] == "nosniff"


def test_invalid_claim_and_unknown_file_cannot_serve_arbitrary_paths():
    assert client.get("/claims/not-a-claim").status_code == 422
    assert client.get("/claims/claim-001/files/not-a-hash/raw").status_code == 404


def test_run_requires_a_nonempty_explicit_folder_selection():
    response = client.post("/claims/run", json={"claim_ids": []})
    assert response.status_code == 422
    assert client.post("/claims/run", json={"claim_ids": ["unknown"]}).status_code == 422


def test_search_errors_are_explicit_and_never_look_like_empty_success(monkeypatch):
    def denied(_claim, _question):
        raise RuntimeError("Semantic reranking is not available.")

    monkeypatch.setattr(service, "search", denied)
    response = client.post("/claims/claim-001/search", json={"question": "What is still outstanding?"})
    assert response.status_code == 409
    assert "Semantic reranking" in response.json()["detail"]
