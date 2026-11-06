import json
from decimal import Decimal

import pdfplumber
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import standalone_api
from app.schemas.claim_operations import ClaimRecord, ClaimsDataset
from app.services import claim_operations_service as service

client = TestClient(standalone_api.app)


def test_six_authored_records_match_claim_and_policy_sources():
    dataset = service.load_dataset()
    review = json.loads((service.EVIDENCE_ROOT / "review-notes.json").read_text(encoding="utf-8"))
    assert dataset.synthetic is True
    assert len(dataset.claims) == 6
    assert dataset.as_of.isoformat() == "2026-11-05T18:00:00+00:00"
    expected = {claim["claim_id"]: claim for claim in review["claims"]}
    for claim in dataset.claims:
        reference = expected[claim.claim_id]
        assert claim.claim_number == reference["claim_number"]
        assert claim.insured_name == reference["insured"]
        assert claim.loss_date.isoformat() == reference["loss_date"]
        assert service.financial_snapshot(claim).outstanding_reserve_total == Decimal(reference["reserve"])
        with pdfplumber.open(service.EVIDENCE_ROOT / claim.policy.source_ref) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        assert claim.policy.policy_number in text
        assert f"USD {claim.policy.specimen_limit:,.2f}" in text
        assert f"USD {claim.policy.specimen_deductible:,.2f}" in text
        assert "2026-01-01 to 2026-12-31" in text


def test_money_totals_exclude_pending_and_voided_requests():
    financials = [service.financial_snapshot(claim) for claim in service.load_dataset().claims]
    assert sum(item.outstanding_reserve_total for item in financials) == Decimal("174500.00")
    assert sum(item.paid_total for item in financials) == Decimal("2500.00")
    assert sum(item.pending_payment_total for item in financials) == Decimal("2250.00")
    assert sum(item.voided_request_total for item in financials) == Decimal("200.00")
    assert sum(item.incurred_total for item in financials) == Decimal("177000.00")
    assert all(item.approved_settlement_amount is None for item in financials)


def test_tool_snapshot_has_exact_decimal_strings_and_synthetic_provenance():
    response = client.get("/claims-operations/claims/claim-006")
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["synthetic"] is True
    assert payload["metadata"]["source_system"] == "simulated_databricks_genie"
    assert payload["metadata"]["implementation"] == "local_read_only_api"
    data = payload["data"]
    assert data["financials"]["outstanding_reserve_total"] == "68000.00"
    assert data["financials"]["paid_expense_total"] == "1100.00"
    assert data["financials"]["paid_indemnity_total"] == "0.00"
    assert data["financials"]["incurred_total"] == "69100.00"
    assert data["financials"]["approved_settlement_amount"] is None
    assert "inspection_estimate" not in data["financials"]
    assert "review_questions" not in response.text


def test_claim_number_alias_resolves_to_the_same_snapshot():
    by_id = client.get("/claims-operations/claims/claim-001").json()
    by_number = client.get("/claims-operations/claims/AV-26-004181").json()
    assert by_id == by_number
    assert client.get("/claims-operations/claims/unknown").status_code == 404


def test_operational_lists_are_filtered_and_validate_inputs():
    auto = client.get("/claims-operations/claims?line_of_business=commercial_auto")
    assert auto.status_code == 200
    assert [claim["claim_id"] for claim in auto.json()["data"]] == ["claim-003"]
    assert client.get("/claims-operations/claims?status=closed").json()["data"] == []
    assert client.get("/claims-operations/claims?status=guess").status_code == 422


def test_activity_overdue_status_uses_snapshot_not_wall_clock():
    payload = client.get("/claims-operations/claims/claim-001/activities?blocking_only=true").json()
    assert len(payload["data"]) == 2
    statuses = {activity["activity_id"]: activity["overdue_as_of_snapshot"] for activity in payload["data"]}
    assert statuses == {"ACT-001-01": True, "ACT-001-02": False}
    complete = client.get("/claims-operations/claims/claim-001/activities?status=completed").json()["data"]
    assert len(complete) == 1
    assert complete[0]["currently_blocking"] is False
    assert complete[0]["overdue_as_of_snapshot"] is False


def test_log_notes_are_bounded_newest_first_and_reference_real_activities():
    payload = client.get("/claims-operations/claims/claim-003/log-notes?limit=1").json()
    assert [note["note_id"] for note in payload["data"]] == ["NOTE-003-03"]
    assert client.get("/claims-operations/claims/claim-003/log-notes?limit=0").status_code == 422
    assert client.get("/claims-operations/claims/claim-003/log-notes?limit=51").status_code == 422
    for claim in service.load_dataset().claims:
        ids = {activity.activity_id for activity in claim.activities}
        assert all(note.activity_id is None or note.activity_id in ids for note in claim.log_notes)


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_the_tool_does_not_mutate_claims(method):
    response = getattr(client, method)("/claims-operations/claims/claim-001")
    assert response.status_code == 405


def test_invalid_dataset_is_an_explicit_failure_not_a_successful_empty_result(tmp_path, monkeypatch, caplog):
    invalid = tmp_path / "claims.json"
    invalid.write_text('{"synthetic":false}', encoding="utf-8")
    monkeypatch.setattr(service, "DATA_PATH", invalid)
    response = client.get("/claims-operations/claims")
    assert response.status_code == 500
    assert "invalid" in response.json()["detail"]
    assert "Structured claims dataset" in caplog.text


def test_dataset_rejects_future_records_and_bad_note_relationships():
    data = service.load_dataset().model_dump(mode="json")
    data["claims"][0]["log_notes"][0]["activity_id"] = "missing"
    with pytest.raises(ValidationError, match="unknown activity"):
        ClaimsDataset.model_validate(data)
    data = service.load_dataset().model_dump(mode="json")
    data["as_of"] = "2026-11-01T00:00:00Z"
    with pytest.raises(ValidationError, match="newer than"):
        ClaimsDataset.model_validate(data)


def test_cross_claim_evidence_references_are_rejected(tmp_path, monkeypatch):
    data = service.load_dataset().model_dump(mode="json")
    data["claims"][0]["policy"]["source_ref"] = "claim-001/../claim-002/policy.pdf"
    invalid = tmp_path / "claims.json"
    invalid.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(service, "DATA_PATH", invalid)
    with pytest.raises(ValueError, match="Invalid evidence reference"):
        service.load_dataset()


def test_decimal_arithmetic_does_not_use_binary_float_rounding():
    data = service.load_dataset().claims[0].model_dump(mode="json")
    first = data["financials"]["payments"][0]
    data["financials"]["payments"] = [
        {**first, "payment_id": "P-1", "amount": "0.10"},
        {**first, "payment_id": "P-2", "amount": "0.20"},
    ]
    claim = ClaimRecord.model_validate(data)
    assert service.financial_snapshot(claim).paid_total == Decimal("0.30")


def test_openapi_exposes_read_only_tool_operations():
    schema = client.get("/openapi.json").json()
    paths = {path: operations for path, operations in schema["paths"].items() if path.startswith("/claims-operations")}
    assert len(paths) == 5
    assert all(set(operations) == {"get"} for operations in paths.values())
    ids = {operations["get"]["operationId"] for operations in paths.values()}
    assert "get_structured_claim_snapshot" in ids
    assert len(ids) == len(paths)
