from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import labeled_analyzer
from app.services import labeled_analyzer_service as service
from app.services import labeling_workspace_service as workspace


legacy_app = FastAPI()
legacy_app.include_router(labeled_analyzer.router)
client = TestClient(legacy_app)


def test_status_and_samples_are_available_without_azure():
    status = client.get("/labeled-analyzer/status")
    samples = client.get("/labeled-analyzer/samples")

    assert status.status_code == 200
    assert status.json()["model"] == "gpt-5.2"
    assert samples.status_code == 200
    assert [item["file_name"] for item in samples.json()] == list(service.HOLDOUT_FILES)
    assert samples.json()[-1]["challenge"] == "handwritten"


def test_sample_pdf_rejects_training_file():
    response = client.get("/labeled-analyzer/samples/ClaimForm_1.pdf/raw")

    assert response.status_code == 400
    assert "not part" in response.json()["detail"]


def test_sample_pdf_serves_holdout():
    response = client.get("/labeled-analyzer/samples/ClaimForm_6.pdf/raw")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")


def test_report_returns_not_found_when_cache_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "REPORT_PATH", tmp_path / "missing.json")

    response = client.get("/labeled-analyzer/report")

    assert response.status_code == 404


def test_cached_stream_returns_report_without_live_evaluation(monkeypatch):
    report = {
        "holdout_files": list(service.HOLDOUT_FILES),
        "repeats": 1,
        "summary": {"labeled_accuracy": 1.0},
    }
    monkeypatch.setattr(service, "load_valid_report", lambda: report)
    monkeypatch.setattr(service, "validate_cached_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service,
        "evaluation_events",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("live evaluation called")),
    )

    response = client.post(
        "/labeled-analyzer/evaluate/stream",
        json={"force_live": False, "repeats": 1},
    )

    assert response.status_code == 200
    assert "event: complete" in response.text
    assert '"labeled_accuracy": 1.0' in response.text


def test_live_stream_delegates_to_evaluation_events(monkeypatch):
    def events(**kwargs):
        assert kwargs["sample_names"] == ("ClaimForm_6.pdf",)
        yield "step", {"step_id": "analyze", "status": "done"}
        yield "complete", {"holdout_files": ["ClaimForm_6.pdf"], "repeats": 1}

    monkeypatch.setattr(service, "evaluation_events", events)
    monkeypatch.setenv("LABELED_ANALYZER_ENABLE_LIVE", "true")
    monkeypatch.setenv("LABELED_ANALYZER_LIVE_COOLDOWN_SECONDS", "0")

    response = client.post(
        "/labeled-analyzer/evaluate/stream",
        json={
            "force_live": True,
            "repeats": 1,
            "sample_names": ["ClaimForm_6.pdf"],
        },
    )

    assert response.status_code == 200
    assert "event: step" in response.text
    assert "event: complete" in response.text


def test_live_stream_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LABELED_ANALYZER_ENABLE_LIVE", raising=False)

    response = client.post(
        "/labeled-analyzer/evaluate/stream",
        json={"force_live": True, "repeats": 1},
    )

    assert response.status_code == 403
    assert "disabled" in response.json()["detail"]


def test_report_rejects_stale_fingerprint(monkeypatch):
    monkeypatch.setattr(
        service,
        "load_valid_report",
        lambda: (_ for _ in ()).throw(ValueError("cached report is stale")),
    )

    response = client.get("/labeled-analyzer/report")

    assert response.status_code == 409
    assert "stale" in response.json()["detail"]


def test_local_project_manual_label_and_export(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(
        workspace,
        "_analyze_document",
        lambda *_args, **_kwargs: {
            "apiVersion": workspace.WORKSPACE_API_VERSION,
            "analyzerId": "prebuilt-layout",
            "contents": [
                {
                    "markdown": "Claim number CL123",
                    "pages": [{"pageNumber": 1}],
                    "fields": {},
                }
            ],
        },
    )

    created = client.post(
        "/labeled-analyzer/projects",
        json={"name": "Customer forms", "analyzer_id": "customerFormsV1"},
    )
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    uploaded = client.post(
        f"/labeled-analyzer/projects/{project_id}/documents",
        data={"role": "training"},
        files=[("files", ("sample.pdf", b"%PDF-1.7\nexample", "application/pdf"))],
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()[0]["document_id"]

    prepared = client.post(
        f"/labeled-analyzer/projects/{project_id}/documents/{document_id}/prepare"
    )
    assert prepared.status_code == 200
    assert prepared.json()["labels"]["ClaimNumber"]["value"] is None

    reviewed = client.put(
        f"/labeled-analyzer/projects/{project_id}/documents/{document_id}/labels",
        json={
            "reviewed": True,
            "labels": {
                "ClaimNumber": {
                    "value": "CL123",
                    "spans": [{"offset": 13, "length": 5}],
                }
            },
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["reviewed"] is True

    exported = client.get(f"/labeled-analyzer/projects/{project_id}/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"] == "application/zip"
    assert exported.content.startswith(b"PK")