from decimal import Decimal
from copy import deepcopy
import json

import pytest

from app.services import labeled_analyzer_service as service


def test_frozen_split_is_disjoint_and_resolves_existing_files():
    service.validate_split()

    assert len(service.TRAINING_FILES) == 5
    assert len(service.HOLDOUT_FILES) == 3
    assert all(service.assert_training_file(name).is_file() for name in service.TRAINING_FILES)
    assert all(service.assert_holdout_file(name).is_file() for name in service.HOLDOUT_FILES)


def test_split_rejects_overlap():
    with pytest.raises(ValueError, match="overlap"):
        service.validate_split(["ClaimForm_1.pdf"], ["ClaimForm_1.pdf"])


def test_claim_path_rejects_traversal_and_training_leakage():
    with pytest.raises(ValueError, match="plain claim PDF"):
        service.assert_holdout_file("../ClaimForm_6.pdf")
    with pytest.raises(ValueError, match="not part"):
        service.assert_training_file("ClaimForm_6.pdf")


def test_training_blob_inventory_contains_no_holdouts(monkeypatch):
    monkeypatch.setattr(service, "storage_prefix", lambda: "training/v1/")

    blob_names = service.expected_training_blob_names()

    assert len(blob_names) == 15
    assert all(name.startswith("training/v1/ClaimForm_") for name in blob_names)
    assert not any(holdout in blob_name for holdout in service.HOLDOUT_FILES for blob_name in blob_names)


def test_resolve_holdouts_rejects_duplicates_and_training_files():
    with pytest.raises(ValueError, match="unique"):
        service.resolve_holdouts(["ClaimForm_6.pdf", "ClaimForm_6.pdf"])
    with pytest.raises(ValueError, match="not part"):
        service.resolve_holdouts(["ClaimForm_1.pdf"])


@pytest.mark.parametrize(
    ("field_name", "left", "right"),
    [
        ("PolicyholderFirstName", " Sophia ", "sophia"),
        ("TelephoneNumber", "(602) 555-1034", "602-555-1034"),
        ("PolicyNumber", "PH-789 0123", "ph7890123"),
        ("PolicyEffectiveDate", "12/05/2020", "2020-12-05"),
        ("TimeOfLoss", "5:10 PM", "17:10:00"),
        ("DamageDeductibleAmount", "$2,000.00", Decimal("2000")),
        ("PropertyAddress", "7788 Spruce St., Phoenix, AZ 85001", "7788 spruce st phoenix az 85001"),
    ],
)
def test_values_match_by_field_type(field_name, left, right):
    assert service.values_match(field_name, left, right)


def test_content_field_value_reads_typed_cu_values():
    assert service.content_field_value({"type": "date", "valueDate": "2023-03-15"}) == "2023-03-15"
    assert service.content_field_value({"type": "number", "valueNumber": 2000}) == 2000
    assert service.content_field_value({"type": "array", "valueArray": []}) is None


def test_score_document_counts_high_confidence_false_accept():
    expected = {field_name: None for field_name in service.FIELD_TYPES}
    expected.update(
        {
            "PolicyholderFirstName": "Isabella",
            "ClaimNumber": "CLM3210987",
        }
    )
    predicted = {
        "PolicyholderFirstName": {"value": "Isabella", "confidence": 0.92},
        "ClaimNumber": {"value": "CLM3210981", "confidence": 0.95},
    }

    score = service.score_document(expected, predicted)

    assert score["correct_fields"] == len(service.FIELD_TYPES) - 1
    assert score["missing_fields"] == len(service.FIELD_TYPES) - 2
    assert score["thresholds"]["0.90"]["accepted"] == 2
    assert score["thresholds"]["0.90"]["false_accepts"] == 1
    assert score["thresholds"]["0.95"]["false_accepts"] == 1


def test_ground_truth_matches_frozen_split_and_schema():
    manifest = service.load_ground_truth()

    assert tuple(manifest["training_files"]) == service.TRAINING_FILES
    assert tuple(manifest["holdout_files"]) == service.HOLDOUT_FILES
    assert manifest["documents"]["claimform_handwritten_1.pdf"]["challenge"] == "handwritten"


def test_labeled_resource_only_adds_knowledge_source():
    container_url = "https://example.blob.core.windows.net/cu-labeled-claims?sig=secret"
    zero_shot = service.build_analyzer_resource()
    labeled = service.build_analyzer_resource(labeled_data_container_url=container_url)

    service.assert_analyzer_parity(zero_shot, labeled)
    assert zero_shot["models"]["completion"] == "gpt-5.2"
    assert labeled["knowledgeSources"][0]["prefix"] == "training/v1/"
    assert service.redact_url(container_url) == "https://example.blob.core.windows.net/cu-labeled-claims"


def test_labeled_resource_rejects_local_path():
    with pytest.raises(ValueError, match="Azure Blob"):
        service.build_analyzer_resource(labeled_data_container_url=r"C:\training")


def test_dedicated_container_and_sas_expiry_are_enforced(monkeypatch):
    monkeypatch.setenv("LABELED_ANALYZER_STORAGE_CONTAINER", "shared-container")
    with pytest.raises(ValueError, match="dedicated"):
        service.storage_container_name()

    monkeypatch.delenv("LABELED_ANALYZER_STORAGE_CONTAINER")
    with pytest.raises(ValueError, match="between 5 and 120"):
        service.create_labeled_data_sas(expiry_minutes=121)


def test_existing_analyzer_is_deep_compared():
    expected = service.build_analyzer_resource(
        labeled_data_container_url="https://example.blob.core.windows.net/cu-labeled-claims?sig=one"
    )
    existing = deepcopy(expected)
    existing["status"] = "ready"
    existing["config"]["serviceAddedDefault"] = None
    existing["knowledgeSources"][0]["containerUrl"] = (
        "https://example.blob.core.windows.net/cu-labeled-claims?sig=two"
    )

    service._validate_existing_analyzer(existing, expected=expected)

    existing["knowledgeSources"][0]["prefix"] = "holdout/"
    with pytest.raises(ValueError, match="frozen experiment"):
        service._validate_existing_analyzer(existing, expected=expected)


class _Blob:
    def __init__(self, name):
        self.name = name


class _Container:
    def __init__(self, names):
        self.names = list(names)
        self.deleted = []

    def list_blobs(self, name_starts_with):
        return [_Blob(name) for name in self.names if name.startswith(name_starts_with)]

    def delete_blob(self, name):
        self.deleted.append(name)
        self.names.remove(name)


def test_remote_inventory_rejects_and_clears_unexpected_holdout(monkeypatch):
    monkeypatch.setattr(service, "storage_prefix", lambda: "training/v1/")
    expected = list(service.expected_training_blob_names())
    contamination = "training/v1/ClaimForm_6.pdf"
    container = _Container([*expected, contamination])

    with pytest.raises(ValueError, match="unexpected"):
        service.verify_remote_training_inventory(container)

    service._clear_training_prefix(container)
    assert contamination in container.deleted
    assert container.names == []


def test_cache_persists_projection_without_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "CU_OUTPUT_DIR", tmp_path)
    payload = _payload("ClaimForm_6.pdf")
    payload["contents"][0]["markdown"] = "full OCR text must not be cached"

    path = service.save_cached_payload("ClaimForm_6.pdf", "zero_shot", payload)
    cached_text = path.read_text(encoding="utf-8")
    cached = service.load_cached_payload("ClaimForm_6.pdf", "zero_shot")

    assert "full OCR text" not in cached_text
    assert cached["cache_version"] == 1
    assert service.project_payload(cached)["fields"]["ClaimNumber"]["value"] == "CLM3210987"


def test_cached_report_fingerprint_detects_staleness():
    payloads = {
        variant: {file_name: [_payload(file_name)] for file_name in service.HOLDOUT_FILES}
        for variant in ("zero_shot", "labeled")
    }
    report = service.build_report(payloads, repeats=1)
    service.validate_cached_report(
        report,
        sample_names=service.HOLDOUT_FILES,
        repeats=1,
    )

    report["experiment_fingerprint"]["digest"] = "stale"
    with pytest.raises(ValueError, match="stale"):
        service.validate_cached_report(
            report,
            sample_names=service.HOLDOUT_FILES,
            repeats=1,
        )


def _field(field_name, value, confidence=0.92, *, offset=0, length=1):
    field_type = service.FIELD_TYPES[field_name]
    value_key = {
        "string": "valueString",
        "date": "valueDate",
        "time": "valueTime",
        "number": "valueNumber",
    }[field_type]
    return {
        "type": field_type,
        value_key: value,
        "confidence": confidence,
        "source": "D(1,0,0,1,1)",
        "spans": [{"offset": offset, "length": length}],
    }


def _triplet_payloads(fields):
    markdown_parts = []
    labels = {}
    offset = 0
    for name, value in fields.items():
        text = str(value)
        markdown_parts.append(text)
        labels[name] = {
            **_field(name, value, offset=offset, length=len(text)),
            "kind": "confirmed",
        }
        offset += len(text) + 1
    markdown = "\n".join(markdown_parts)
    result = {
        "status": "Succeeded",
        "result": {
            "apiVersion": service.API_VERSION,
            "contents": [
                {
                    "markdown": markdown,
                    "pages": [{"pageNumber": 1}],
                }
            ],
        },
    }
    label_payload = {
        "$schema": f"https://schema.ai.azure.com/mmi/{service.API_VERSION}/labels.json",
        "fileId": "",
        "metadata": {"mimeType": "application/pdf"},
        "fieldLabels": labels,
    }
    return label_payload, result


def _payload(file_name, *, wrong_claim_number=False):
    truth = service.load_ground_truth()["documents"][file_name]["fields"]
    fields = {
        name: _field(name, value)
        for name, value in truth.items()
    }
    if wrong_claim_number:
        fields["ClaimNumber"] = _field("ClaimNumber", "WRONG", confidence=0.95)
    return {
        "analyzerId": "test",
        "apiVersion": service.API_VERSION,
        "contents": [{"fields": fields}],
    }


def test_validates_complete_local_training_triplets(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "LABELED_DATA_DIR", tmp_path)
    truth = service.load_ground_truth()["documents"]
    for file_name in service.TRAINING_FILES:
        labels, result = _triplet_payloads(truth[file_name]["fields"])
        (tmp_path / f"{file_name}.labels.json").write_text(json.dumps(labels), encoding="utf-8")
        (tmp_path / f"{file_name}.result.json").write_text(json.dumps(result), encoding="utf-8")

    triplets = service.validate_label_triplets()

    assert len(triplets) == 5
    assert service.labeled_data_status()["ready"] is True


def test_triplet_validation_rejects_label_disagreement(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "LABELED_DATA_DIR", tmp_path)
    file_name = service.TRAINING_FILES[0]
    truth = service.load_ground_truth()["documents"][file_name]["fields"]
    labels, result = _triplet_payloads(truth)
    labels["fieldLabels"]["ClaimNumber"]["valueString"] = "WRONG"
    labels["fieldLabels"]["ClaimNumber"]["kind"] = "corrected"
    (tmp_path / f"{file_name}.labels.json").write_text(json.dumps(labels), encoding="utf-8")
    (tmp_path / f"{file_name}.result.json").write_text(
        json.dumps(result),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="disagrees with ground truth"):
        service.validate_label_triplets()


def test_triplet_validation_rejects_swapped_ocr_result(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "LABELED_DATA_DIR", tmp_path)
    truth = service.load_ground_truth()["documents"]
    first = service.TRAINING_FILES[0]
    second = service.TRAINING_FILES[1]
    for file_name in service.TRAINING_FILES:
        labels, result = _triplet_payloads(truth[file_name]["fields"])
        if file_name == first:
            _, result = _triplet_payloads(truth[second]["fields"])
        (tmp_path / f"{file_name}.labels.json").write_text(json.dumps(labels), encoding="utf-8")
        (tmp_path / f"{file_name}.result.json").write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(ValueError, match="OCR span"):
        service.validate_label_triplets()


def test_build_report_measures_accuracy_not_confidence():
    zero_shot = {
        file_name: [_payload(file_name, wrong_claim_number=file_name == "ClaimForm_6.pdf")]
        for file_name in service.HOLDOUT_FILES
    }
    labeled = {
        file_name: [_payload(file_name)]
        for file_name in service.HOLDOUT_FILES
    }

    report = service.build_report(
        {"zero_shot": zero_shot, "labeled": labeled},
        repeats=1,
    )

    assert report["summary"]["zero_shot_accuracy"] == pytest.approx(55 / 56)
    assert report["summary"]["labeled_accuracy"] == 1.0
    assert report["summary"]["accuracy_delta_points"] == pytest.approx(100 / 56)
    assert report["variants"]["zero_shot"]["aggregate"]["document_weighted_accuracy"] == pytest.approx(41 / 42)
    assert report["holdout_unique_claims"] == 2
    assert report["training_unique_claims"] == 4
    assert report["summary"]["zero_shot_false_accepts_at_090"] == 1
    assert report["summary"]["labeled_false_accepts_at_090"] == 0