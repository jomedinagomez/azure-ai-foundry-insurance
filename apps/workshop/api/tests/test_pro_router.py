"""Router-level smoke tests (mocks the CU calls)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.routers import pro as pro_router
from app.schemas.pro import (
    ProClaimsFields,
    ProClaimsResult,
    ProFraudFields,
    ProFraudResult,
    ProMeta,
)
from app.services import pro_service
from fastapi import FastAPI


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(pro_router.router)
    return TestClient(app)


def test_healthcheck_returns_shape(client):
    with patch.object(pro_service, "healthcheck", return_value={
        "api_version": pro_service.API_VERSION,
        "endpoint_configured": True,
        "analyzers": {pro_service.ANALYZER_CLAIMS_ID: True, pro_service.ANALYZER_FRAUD_ID: False},
        "samples_available": ["claim_auto_collision"],
        "pro_mode_supported": True,
        "error": None,
    }):
        r = client.get("/pro/healthcheck")
    assert r.status_code == 200
    body = r.json()
    assert body["api_version"] == pro_service.API_VERSION
    assert body["analyzers"][pro_service.ANALYZER_CLAIMS_ID] is True


def test_list_samples_includes_both_bundled(client):
    r = client.get("/pro/samples")
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()}
    assert {"claim_auto_collision", "claim_auto_collision_fraud"}.issubset(ids)


def test_analyze_sample_claims_path(client):
    fake = ProClaimsResult(
        meta=ProMeta(
            sample_id="claim_auto_collision",
            scenario="claims",
            analyzer_id=pro_service.ANALYZER_CLAIMS_ID,
            api_version=pro_service.API_VERSION,
            elapsed_sec=1.23,
            input_files=["claim_form.pdf", "police_report.pdf", "repair_estimate.pdf", "damage_photo.png"],
        ),
        fields=ProClaimsFields(
            claimant_name="Sarah J. Whitfield",
            policy_number="PA-7421-2026",
            estimated_total=8500.0,
            coverage_applies="Yes",
            police_report_present="Yes",
            document_set_completeness="Complete",
        ),
        raw={},
    )
    with patch.object(pro_service, "analyze_claims", return_value=fake):
        r = client.post("/pro/samples/claim_auto_collision/analyze?scenario=claims")
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["scenario"] == "claims"
    assert body["fields"]["coverage_applies"] == "Yes"


def test_analyze_sample_fraud_path(client):
    fake = ProFraudResult(
        meta=ProMeta(
            sample_id="claim_auto_collision_fraud",
            scenario="fraud",
            analyzer_id=pro_service.ANALYZER_FRAUD_ID,
            api_version=pro_service.API_VERSION,
            elapsed_sec=2.5,
            input_files=["claim_form.pdf", "police_report.pdf", "repair_estimate.pdf", "damage_photo.png"],
        ),
        fields=ProFraudFields(overall_fraud_indication="High"),
        cu_signals=[],
        rule_signals=[],
        risk_score=85,
        risk_band="high",
        raw={},
    )
    with patch.object(pro_service, "analyze_fraud", return_value=fake):
        r = client.post("/pro/samples/claim_auto_collision_fraud/analyze?scenario=fraud")
    assert r.status_code == 200
    body = r.json()
    assert body["risk_band"] == "high"
    assert body["risk_score"] == 85


def test_analyze_sample_unknown_returns_404(client):
    r = client.post("/pro/samples/does_not_exist/analyze?scenario=claims")
    assert r.status_code == 404


def test_analyze_upload_requires_files(client):
    r = client.post("/pro/claims/analyze")
    assert r.status_code == 422  # FastAPI: missing required form field
