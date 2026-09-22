import json
from io import BytesIO
import zipfile

import pytest

from app.services import labeling_workspace_service as workspace


@pytest.fixture
def local_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE_ROOT", tmp_path)
    return tmp_path


def _pdf(marker="default") -> bytes:
    return f"%PDF-1.7\nsynthetic test document {marker}".encode()


def _result(markdown="Yasmin\nPH954738"):
    return {
        "apiVersion": "2025-11-01",
        "analyzerId": "formsDemoV1",
        "contents": [{"markdown": markdown, "pages": [{"pageNumber": 1}], "fields": {}}],
    }


def _field(field_type, value, *, offset=0, length=1, confidence=0.9):
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


def test_local_project_upload_review_and_export(local_workspace):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")
    assert project["base_analyzer_id"].endswith(project["project_id"])
    assert project["trained_analyzer_id"].endswith(project["project_id"])
    assert project["base_analyzer_id"] != project["trained_analyzer_id"]
    created = workspace.add_documents(
        project["project_id"],
        [("sample.pdf", _pdf(), "application/pdf")],
        role="training",
    )
    document_id = created[0]["document_id"]
    result_path = workspace._document_dir(project["project_id"], document_id) / "result.json"
    result_path.write_text(json.dumps(_result()), encoding="utf-8")

    reviewed = workspace.save_document_labels(
        project["project_id"],
        document_id,
        {
            "PolicyholderFirstName": {
                "value": "Yasmin",
                "spans": [{"offset": 0, "length": 6}],
            },
            "PolicyNumber": {
                "value": "PH954738",
                "spans": [{"offset": 7, "length": 8}],
            },
        },
        reviewed=True,
    )

    assert reviewed["status"] == "reviewed"
    assert workspace.get_project(project["project_id"])["summary"]["reviewed_count"] == 1

    file_name, content = workspace.export_project(project["project_id"])
    assert file_name.endswith("-labeled-data.zip")
    with zipfile.ZipFile(BytesIO(content)) as archive:
        names = set(archive.namelist())
        labels = json.loads(archive.read("training/sample.pdf.labels.json"))
        assert "training/sample.pdf" in names
        assert "training/sample.pdf.result.json" in names
        assert labels["fieldLabels"]["PolicyNumber"]["valueString"] == "PH954738"


def test_review_rejects_ungrounded_manual_value(local_workspace):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")
    document = workspace.add_documents(
        project["project_id"],
        [("sample.pdf", _pdf(), "application/pdf")],
        role="evaluation",
    )[0]

    with pytest.raises(ValueError, match="needs a source or OCR span"):
        workspace.save_document_labels(
            project["project_id"],
            document["document_id"],
            {"ClaimNumber": {"value": "CL123"}},
            reviewed=True,
        )


def test_document_names_and_roles_are_validated(local_workspace):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")

    with pytest.raises(ValueError, match="training or evaluation"):
        workspace.add_documents(project["project_id"], [("a.pdf", _pdf(), None)], role="holdout")
    with pytest.raises(ValueError, match="plain .pdf"):
        workspace.add_documents(project["project_id"], [("../a.pdf", _pdf(), None)], role="training")
    with pytest.raises(ValueError, match="nonempty PDF"):
        workspace.add_documents(project["project_id"], [("a.pdf", b"not a pdf", None)], role="training")


def test_duplicate_bytes_cannot_cross_training_and_evaluation(local_workspace):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")
    workspace.add_documents(
        project["project_id"], [("train.pdf", _pdf("same"), None)], role="training"
    )

    with pytest.raises(ValueError, match="duplicates"):
        workspace.add_documents(
            project["project_id"],
            [("renamed-evaluation.pdf", _pdf("same"), None)],
            role="evaluation",
        )


def test_auto_label_updates_only_selected_document(local_workspace, monkeypatch):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")
    documents = workspace.add_documents(
        project["project_id"],
        [("one.pdf", _pdf("one"), None), ("two.pdf", _pdf("two"), None)],
        role="training",
    )
    payload = _result("Yasmin\nPH954738")
    payload["contents"][0]["fields"] = {
        "PolicyholderFirstName": _field("string", "Yasmin", offset=0, length=6),
        "PolicyNumber": _field("string", "PH954738", offset=7, length=8),
    }
    monkeypatch.setattr(workspace, "_analyze_document", lambda *_args, **_kwargs: payload)

    labeled = workspace.auto_label_document(
        project["project_id"],
        documents[0]["document_id"],
    )
    untouched = workspace.load_document(project["project_id"], documents[1]["document_id"])

    assert labeled["labels"]["PolicyNumber"]["value"] == "PH954738"
    assert labeled["labels"]["PolicyNumber"]["kind"] == "confirmed"
    assert labeled["reviewed"] is False
    assert untouched["status"] == "uploaded"


def test_manual_prepare_produces_ocr_without_field_values(local_workspace, monkeypatch):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")
    document = workspace.add_documents(
        project["project_id"],
        [("manual.pdf", _pdf(), None)],
        role="training",
    )[0]
    payload = _result("Select this OCR text")
    payload["contents"][0]["fields"] = {
        "ClaimNumber": _field("string", "SHOULD-NOT-BE-COPIED", length=20)
    }
    monkeypatch.setattr(workspace, "_analyze_document", lambda *_args, **_kwargs: payload)

    prepared = workspace.prepare_document_for_manual_labeling(
        project["project_id"],
        document["document_id"],
    )

    assert prepared["status"] == "ready_for_labeling"
    assert prepared["markdown"] == "Select this OCR text"
    assert prepared["labels"]["ClaimNumber"]["value"] is None


def test_labeling_actions_do_not_overwrite_existing_work(local_workspace, monkeypatch):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")
    document = workspace.add_documents(
        project["project_id"], [("manual.pdf", _pdf("manual"), None)], role="training"
    )[0]
    result_path = workspace._document_dir(project["project_id"], document["document_id"]) / "result.json"
    result_path.write_text(json.dumps(_result("CL123")), encoding="utf-8")
    workspace.save_document_labels(
        project["project_id"],
        document["document_id"],
        {"ClaimNumber": {"value": "CL123", "spans": [{"offset": 0, "length": 5}]}},
        reviewed=True,
    )
    monkeypatch.setattr(
        workspace,
        "_analyze_document",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Azure called")),
    )

    with pytest.raises(ValueError, match="already contains labeling work"):
        workspace.prepare_document_for_manual_labeling(
            project["project_id"], document["document_id"]
        )
    with pytest.raises(ValueError, match="already contains labeling work"):
        workspace.auto_label_document(project["project_id"], document["document_id"])


def test_evaluation_truth_cannot_be_auto_labeled(local_workspace, monkeypatch):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")
    document = workspace.add_documents(
        project["project_id"], [("evaluation.pdf", _pdf("eval"), None)], role="evaluation"
    )[0]
    monkeypatch.setattr(
        workspace,
        "_analyze_document",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Azure called")),
    )

    with pytest.raises(ValueError, match="independently"):
        workspace.auto_label_document(project["project_id"], document["document_id"])


def test_label_edit_invalidates_saved_evaluation(local_workspace):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")
    document = workspace.add_documents(
        project["project_id"], [("evaluation.pdf", _pdf("eval"), None)], role="evaluation"
    )[0]
    result_path = workspace._document_dir(project["project_id"], document["document_id"]) / "result.json"
    result_path.write_text(json.dumps(_result("CL123")), encoding="utf-8")
    workspace.save_document_labels(
        project["project_id"],
        document["document_id"],
        {"ClaimNumber": {"value": "CL123", "spans": [{"offset": 0, "length": 5}]}},
        reviewed=True,
    )
    evaluation_path = workspace._project_dir(project["project_id"]) / "evaluation.json"
    evaluation_path.write_text(json.dumps({"stale": True}), encoding="utf-8")

    workspace.save_document_labels(
        project["project_id"],
        document["document_id"],
        {"ClaimNumber": {"value": "CL124", "spans": [{"offset": 0, "length": 5}]}},
        reviewed=True,
    )

    assert not evaluation_path.exists()
    assert workspace.get_project(project["project_id"])["evaluation"] is None


def test_analyzer_ownership_prevents_cross_project_replacement(local_workspace):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")
    existing = {"tags": {"demo": "local-labeling-workspace", "project": "another-project"}}

    with pytest.raises(ValueError, match="owned by another project"):
        workspace._assert_analyzer_ownership(existing, workspace.load_project(project["project_id"]))


def test_score_uses_reviewed_evaluation_truth_only(local_workspace, monkeypatch):
    project = workspace.create_project(name="Forms demo", analyzer_id="formsDemoV1")
    documents = workspace.add_documents(
        project["project_id"],
        [("train.pdf", _pdf("train"), None)],
        role="training",
    )
    documents += workspace.add_documents(
        project["project_id"],
        [("evaluate.pdf", _pdf("evaluate"), None)],
        role="evaluation",
    )
    for index, document in enumerate(documents):
        result_path = workspace._document_dir(project["project_id"], document["document_id"]) / "result.json"
        result_path.write_text(json.dumps(_result("CL123")), encoding="utf-8")
        workspace.save_document_labels(
            project["project_id"],
            document["document_id"],
            {"ClaimNumber": {"value": "CL123", "spans": [{"offset": 0, "length": 5}]}},
            reviewed=True,
        )
    stored = workspace.load_project(project["project_id"])
    stored["analyzers"]["base"]["status"] = "ready"
    stored["analyzers"]["trained"]["status"] = "ready"
    workspace._save_project(stored)

    def analyze(_bytes, *, analyzer_id):
        value = "CL123" if "Labeled" in analyzer_id else "CL999"
        payload = _result(value)
        payload["contents"][0]["fields"] = {
            "ClaimNumber": _field("string", value, length=len(value))
        }
        return payload

    monkeypatch.setattr(workspace, "_analyze_document", analyze)
    report = workspace.score_project(project["project_id"])

    assert report["evaluation_documents"] == 1
    assert report["summary"]["zero_shot_accuracy"] == 0.0
    assert report["summary"]["labeled_accuracy"] == 1.0
    assert list(report["documents"].values())[0]["file_name"] == "evaluate.pdf"