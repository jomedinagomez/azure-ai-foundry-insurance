"""Local document-labeling projects for the workshop UI."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4
import zipfile

from app.services import labeled_analyzer_service as analyzer_service


REPO_ROOT = Path(__file__).resolve().parents[5]
WORKSPACE_ROOT = Path(
    os.environ.get("LABELING_WORKSPACE_ROOT")
    or REPO_ROOT / ".workbench" / "labeled-analyzer"
).resolve()
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_DOCUMENTS = 40
WORKSPACE_API_VERSION = "2026-06-01-preview"
PROJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")
DOCUMENT_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")
ANALYZER_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,47}$")
VALUE_KEYS = {
    "string": "valueString",
    "date": "valueDate",
    "time": "valueTime",
    "number": "valueNumber",
    "integer": "valueInteger",
    "boolean": "valueBoolean",
}


def forms_field_schema() -> dict[str, Any]:
    return deepcopy(analyzer_service.load_analyzer_template()["fieldSchema"])


def create_project(*, name: str, analyzer_id: str) -> dict[str, Any]:
    name = name.strip()
    analyzer_id = analyzer_id.strip()
    if not name or len(name) > 80:
        raise ValueError("Project name must be between 1 and 80 characters.")
    if not ANALYZER_ID_PATTERN.fullmatch(analyzer_id):
        raise ValueError(
            "Analyzer ID must start with a letter and contain 3-48 letters, numbers, '-' or '_'."
        )
    project_id = uuid4().hex[:12]
    base_analyzer_id = f"{analyzer_id}{project_id}"
    trained_analyzer_id = f"{analyzer_id[:36]}Labeled{project_id}"
    now = _utc_now()
    project = {
        "schema_version": 1,
        "project_id": project_id,
        "name": name,
        "preset": "property-claim-form",
        "requested_analyzer_id": analyzer_id,
        "base_analyzer_id": base_analyzer_id,
        "trained_analyzer_id": trained_analyzer_id,
        "field_schema": forms_field_schema(),
        "documents": [],
        "analyzers": {
            "base": {"status": "not_created", "analyzer_id": base_analyzer_id},
            "trained": {"status": "not_created", "analyzer_id": trained_analyzer_id},
        },
        "created_at": now,
        "updated_at": now,
    }
    _project_dir(project_id).mkdir(parents=True, exist_ok=False)
    _documents_dir(project_id).mkdir()
    _write_json(_project_file(project_id), project)
    return project_summary(project)


def list_projects() -> list[dict[str, Any]]:
    projects_dir = WORKSPACE_ROOT / "projects"
    if not projects_dir.is_dir():
        return []
    projects = [
        project_summary(json.loads(path.read_text(encoding="utf-8")))
        for path in projects_dir.glob("*/project.json")
    ]
    return sorted(projects, key=lambda item: item["updated_at"], reverse=True)


def load_project(project_id: str) -> dict[str, Any]:
    path = _project_file(project_id)
    if not path.is_file():
        raise FileNotFoundError(f"Labeling project not found: {project_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_project(project_id: str) -> dict[str, Any]:
    project = load_project(project_id)
    project["summary"] = project_summary(project)
    project["documents"] = [
        document_summary(load_document(project_id, document_id, include_content=False))
        for document_id in project["documents"]
    ]
    evaluation_path = _project_dir(project_id) / "evaluation.json"
    project["evaluation"] = (
        json.loads(evaluation_path.read_text(encoding="utf-8"))
        if evaluation_path.is_file()
        else None
    )
    return project


def project_summary(project: dict[str, Any]) -> dict[str, Any]:
    documents = [
        load_document(project["project_id"], document_id, include_content=False)
        for document_id in project.get("documents", [])
    ]
    return {
        "project_id": project["project_id"],
        "name": project["name"],
        "preset": project["preset"],
        "base_analyzer_id": project["base_analyzer_id"],
        "trained_analyzer_id": project["trained_analyzer_id"],
        "analyzers": project["analyzers"],
        "document_count": len(documents),
        "training_count": sum(item["role"] == "training" for item in documents),
        "evaluation_count": sum(item["role"] == "evaluation" for item in documents),
        "reviewed_count": sum(bool(item.get("reviewed")) for item in documents),
        "updated_at": project["updated_at"],
    }


def add_documents(
    project_id: str,
    uploads: Iterable[tuple[str, bytes, str | None]],
    *,
    role: str,
) -> list[dict[str, Any]]:
    if role not in {"training", "evaluation"}:
        raise ValueError("Document role must be training or evaluation.")
    project = load_project(project_id)
    pending = list(uploads)
    if not pending:
        raise ValueError("Select at least one PDF.")
    if len(project["documents"]) + len(pending) > MAX_DOCUMENTS:
        raise ValueError(f"A project can contain at most {MAX_DOCUMENTS} documents.")

    existing_documents = [
        load_document(project_id, document_id, include_content=False)
        for document_id in project["documents"]
    ]
    existing_names = {item["file_name"].casefold() for item in existing_documents}
    existing_hashes = {
        item.get("sha256")
        or _sha256_bytes(source_path(project_id, item["document_id"]).read_bytes())
        for item in existing_documents
    }
    validated: list[tuple[str, bytes, str]] = []
    for file_name, data, _content_type in pending:
        safe_name = _safe_pdf_name(file_name)
        if safe_name.casefold() in existing_names:
            raise ValueError(f"A document named {safe_name} already exists in this project.")
        if not data or len(data) > MAX_DOCUMENT_BYTES or not data.startswith(b"%PDF-"):
            raise ValueError(f"{safe_name} must be a nonempty PDF smaller than 25 MB.")
        digest = _sha256_bytes(data)
        if digest in existing_hashes:
            raise ValueError(
                f"{safe_name} duplicates a document already in this project; training and evaluation must be disjoint."
            )
        existing_names.add(safe_name.casefold())
        existing_hashes.add(digest)
        validated.append((safe_name, data, digest))

    created = []
    fields = project["field_schema"]["fields"]
    for file_name, data, digest in validated:
        document_id = uuid4().hex[:12]
        directory = _document_dir(project_id, document_id)
        directory.mkdir()
        (directory / "source.pdf").write_bytes(data)
        document = {
            "document_id": document_id,
            "file_name": file_name,
            "sha256": digest,
            "role": role,
            "status": "uploaded",
            "reviewed": False,
            "labels": {
                name: {
                    "type": definition["type"],
                    "value": None,
                    "auto_value": None,
                    "confidence": None,
                    "source": None,
                    "spans": [],
                    "kind": "corrected",
                }
                for name, definition in fields.items()
            },
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        _write_json(directory / "document.json", document)
        project["documents"].append(document_id)
        created.append(document_summary(document))

    _invalidate_evaluation(project)
    _save_project(project)
    return created


def load_document(
    project_id: str, document_id: str, *, include_content: bool = True
) -> dict[str, Any]:
    path = _document_file(project_id, document_id)
    if not path.is_file():
        raise FileNotFoundError(f"Document not found: {document_id}")
    document = json.loads(path.read_text(encoding="utf-8"))
    if include_content:
        result_path = _document_dir(project_id, document_id) / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else None
        document["markdown"] = _result_markdown(result)
    return document


def document_summary(document: dict[str, Any]) -> dict[str, Any]:
    labeled = sum(item.get("value") not in (None, "") for item in document["labels"].values())
    grounded = sum(
        item.get("value") not in (None, "") and bool(item.get("source") or item.get("spans"))
        for item in document["labels"].values()
    )
    return {
        "document_id": document["document_id"],
        "file_name": document["file_name"],
        "role": document["role"],
        "status": document["status"],
        "reviewed": document["reviewed"],
        "labeled_fields": labeled,
        "grounded_fields": grounded,
        "total_fields": len(document["labels"]),
    }


def source_path(project_id: str, document_id: str) -> Path:
    load_document(project_id, document_id, include_content=False)
    return _document_dir(project_id, document_id) / "source.pdf"


def workspace_capabilities() -> dict[str, Any]:
    endpoint = (
        os.environ.get("APP_CONTENT_UNDERSTANDING_ENDPOINT")
        or os.environ.get("CONTENTUNDERSTANDING_ENDPOINT")
        or os.environ.get("FOUNDRY_ENDPOINT")
    )
    storage = os.environ.get("LABELED_ANALYZER_STORAGE_ACCOUNT") or os.environ.get(
        "STORAGE_ACCOUNT_NAME"
    )
    return {
        "api_version": WORKSPACE_API_VERSION,
        "content_understanding_configured": bool(endpoint),
        "host_storage_configured": bool(storage),
        "storage_mode": "host-managed-temporary",
    }


def create_base_analyzer(project_id: str) -> dict[str, Any]:
    project = load_project(project_id)
    analyzer_id = project["base_analyzer_id"]
    resource = build_analyzer_resource(project)
    client = _workspace_client()
    outcome = "created"
    try:
        existing = analyzer_service._as_dict(client.get_analyzer(analyzer_id=analyzer_id))
    except Exception as exc:
        if not _is_not_found(exc):
            raise
    else:
        _assert_analyzer_ownership(existing, project)
        if str(existing.get("status", "ready")).casefold() != "ready":
            raise ValueError(f"Analyzer {analyzer_id} exists but is not ready.")
        if analyzer_service._select_expected_shape(existing, resource) != resource:
            raise ValueError(
                f"Analyzer {analyzer_id} already exists with a different schema. Choose another analyzer ID."
            )
        outcome = "reused"

    if outcome == "created":
        client.begin_create_analyzer(
            analyzer_id=analyzer_id,
            resource=resource,
            allow_replace=False,
        ).result()
    project["analyzers"]["base"] = {
        "status": "ready",
        "analyzer_id": analyzer_id,
        "last_action": outcome,
        "updated_at": _utc_now(),
    }
    _invalidate_evaluation(project)
    _save_project(project)
    return project["analyzers"]["base"]


def prepare_document_for_manual_labeling(
    project_id: str, document_id: str
) -> dict[str, Any]:
    project = load_project(project_id)
    document = load_document(project_id, document_id, include_content=False)
    _assert_unlabeled_document(document)
    payload = _analyze_document(
        source_path(project_id, document_id).read_bytes(),
        analyzer_id="prebuilt-layout",
    )
    if not (_result_content(payload).get("markdown") or "").strip():
        raise ValueError("The layout result has no OCR text for manual labeling.")
    for label in document["labels"].values():
        label.update(
            {
                "value": None,
                "auto_value": None,
                "confidence": None,
                "source": None,
                "spans": [],
                "kind": "corrected",
            }
        )
    document["status"] = "ready_for_labeling"
    document["reviewed"] = False
    document["updated_at"] = _utc_now()
    _write_json(_document_dir(project_id, document_id) / "result.json", payload)
    _write_json(_document_file(project_id, document_id), document)
    _invalidate_evaluation(project)
    _save_project(project)
    return load_document(project_id, document_id)


def auto_label_document(
    project_id: str,
    document_id: str,
    *,
    analyzer_id: str | None = None,
) -> dict[str, Any]:
    project = load_project(project_id)
    document = load_document(project_id, document_id, include_content=False)
    _assert_unlabeled_document(document)
    if document["role"] == "evaluation":
        raise ValueError(
            "Evaluation documents must be labeled independently with Prepare OCR; auto-labeling would seed the truth from a model under test."
        )
    selected_analyzer = (analyzer_id or project["base_analyzer_id"]).strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,63}", selected_analyzer):
        raise ValueError("Auto-label analyzer ID is invalid.")
    payload = _analyze_document(
        source_path(project_id, document_id).read_bytes(),
        analyzer_id=selected_analyzer,
    )
    content = _result_content(payload)
    markdown = content.get("markdown") or ""
    if not markdown.strip():
        raise ValueError("The analyzer result has no OCR text for label grounding.")
    fields = content.get("fields") or {}
    for field_name, label in document["labels"].items():
        field = fields.get(field_name) or {}
        value = analyzer_service.content_field_value(field)
        label.update(
            {
                "value": value,
                "auto_value": value,
                "confidence": field.get("confidence"),
                "source": field.get("source"),
                "spans": field.get("spans") or [],
                "kind": "confirmed",
            }
        )
    document["auto_label_analyzer_id"] = selected_analyzer
    document["status"] = "auto_labeled"
    document["reviewed"] = False
    document["updated_at"] = _utc_now()
    _write_json(_document_dir(project_id, document_id) / "result.json", payload)
    _write_json(_document_file(project_id, document_id), document)
    _invalidate_evaluation(project)
    _save_project(project)
    return load_document(project_id, document_id)


def build_trained_analyzer(project_id: str) -> dict[str, Any]:
    project = load_project(project_id)
    if project["analyzers"]["base"]["status"] != "ready":
        raise ValueError("Create the zero-shot analyzer before building the learned analyzer.")
    training = _reviewed_documents(project, role="training")
    if not training:
        raise ValueError("Review at least one training document before building the learned analyzer.")

    container, container_url = _stage_training_documents(project, training)
    analyzer_id = project["trained_analyzer_id"]
    build_error: Exception | None = None
    try:
        resource = build_analyzer_resource(
            project,
            labeled_data_container_url=_container_sas_url(container.container_name),
        )
        client = _workspace_client()
        allow_replace = False
        try:
            existing = analyzer_service._as_dict(client.get_analyzer(analyzer_id=analyzer_id))
        except Exception as exc:
            if not _is_not_found(exc):
                raise
        else:
            _assert_analyzer_ownership(existing, project)
            allow_replace = True
        client.begin_create_analyzer(
            analyzer_id=analyzer_id,
            resource=resource,
            allow_replace=allow_replace,
        ).result()
    except Exception as exc:
        build_error = exc
        raise
    finally:
        try:
            container.delete_container()
        except Exception as cleanup_exc:
            if build_error is not None:
                build_error.add_note(f"Temporary container cleanup also failed: {cleanup_exc}")
            else:
                raise RuntimeError(
                    "The analyzer was built, but its temporary training container could not be deleted."
                ) from cleanup_exc

    project["analyzers"]["trained"] = {
        "status": "ready",
        "analyzer_id": analyzer_id,
        "training_documents": len(training),
        "staging": "deleted-after-build",
        "host_managed_container": container_url,
        "updated_at": _utc_now(),
    }
    _invalidate_evaluation(project)
    _save_project(project)
    return project["analyzers"]["trained"]


def score_project(project_id: str) -> dict[str, Any]:
    project = load_project(project_id)
    evaluation = _reviewed_documents(project, role="evaluation")
    if not evaluation:
        raise ValueError("Review at least one evaluation document before scoring.")
    if project["analyzers"]["trained"]["status"] != "ready":
        raise ValueError("Build the learned analyzer before scoring it.")
    if project["analyzers"]["base"]["status"] != "ready":
        raise ValueError("Create the zero-shot analyzer before scoring.")

    documents: dict[str, Any] = {}
    totals = {"zero_shot": [0, 0], "labeled": [0, 0]}
    for document in evaluation:
        file_bytes = source_path(project_id, document["document_id"]).read_bytes()
        payloads = {
            "zero_shot": _analyze_document(file_bytes, analyzer_id=project["base_analyzer_id"]),
            "labeled": _analyze_document(file_bytes, analyzer_id=project["trained_analyzer_id"]),
        }
        rows = []
        for field_name, label in document["labels"].items():
            expected = label.get("value")
            if expected in (None, ""):
                continue
            row = {"field_name": field_name, "expected": expected}
            for variant, payload in payloads.items():
                field = (_result_content(payload).get("fields") or {}).get(field_name) or {}
                actual = analyzer_service.content_field_value(field)
                correct = analyzer_service.values_match(field_name, expected, actual)
                totals[variant][0] += int(correct)
                totals[variant][1] += 1
                row[variant] = {
                    "actual": actual,
                    "confidence": field.get("confidence"),
                    "correct": correct,
                    "source": field.get("source"),
                }
            rows.append(row)
        documents[document["document_id"]] = {
            "file_name": document["file_name"],
            "fields": rows,
        }

    def accuracy(variant: str) -> float:
        correct, total = totals[variant]
        return correct / total if total else 0.0

    report = {
        "generated_at": _utc_now(),
        "project_id": project_id,
        "training_documents": len(_reviewed_documents(project, role="training")),
        "evaluation_documents": len(evaluation),
        "zero_shot_analyzer_id": project["base_analyzer_id"],
        "labeled_analyzer_id": project["trained_analyzer_id"],
        "summary": {
            "zero_shot_accuracy": accuracy("zero_shot"),
            "labeled_accuracy": accuracy("labeled"),
            "accuracy_delta_points": (accuracy("labeled") - accuracy("zero_shot")) * 100,
        },
        "documents": documents,
    }
    _write_json(_project_dir(project_id) / "evaluation.json", report)
    project["last_evaluation"] = {
        **report["summary"],
        "generated_at": report["generated_at"],
    }
    _save_project(project)
    return report


def save_document_labels(
    project_id: str,
    document_id: str,
    labels: dict[str, dict[str, Any]],
    *,
    reviewed: bool,
) -> dict[str, Any]:
    project = load_project(project_id)
    document = load_document(project_id, document_id)
    unknown = set(labels) - set(project["field_schema"]["fields"])
    if unknown:
        raise ValueError(f"Unknown label fields: {sorted(unknown)}")
    markdown = document.get("markdown") or ""

    for field_name, update in labels.items():
        current = document["labels"][field_name]
        value = _coerce_value(current["type"], update.get("value"))
        spans = _validate_spans(update.get("spans") or [], markdown)
        source = str(update.get("source") or "").strip() or None
        if reviewed and value not in (None, "") and not source and not spans:
            raise ValueError(f"{field_name} needs a source or OCR span before review.")
        current.update(
            {
                "value": value,
                "source": source,
                "spans": spans,
                "kind": (
                    "confirmed"
                    if current.get("auto_value") == value and value not in (None, "")
                    else "corrected"
                ),
            }
        )

    labeled = [item for item in document["labels"].values() if item.get("value") not in (None, "")]
    if reviewed and not labeled:
        raise ValueError("Review requires at least one labeled field.")
    document["reviewed"] = reviewed
    document["status"] = "reviewed" if reviewed else "draft"
    document["updated_at"] = _utc_now()
    _write_json(_document_file(project_id, document_id), document)
    _invalidate_evaluation(project)
    _save_project(project)
    return load_document(project_id, document_id)


def export_project(project_id: str) -> tuple[str, bytes]:
    project = load_project(project_id)
    reviewed = [
        load_document(project_id, document_id)
        for document_id in project["documents"]
        if load_document(project_id, document_id, include_content=False).get("reviewed")
    ]
    if not reviewed:
        raise ValueError("Review at least one document before export.")

    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = {
            "schema_version": 1,
            "project_id": project_id,
            "name": project["name"],
            "base_analyzer_id": project["base_analyzer_id"],
            "trained_analyzer_id": project["trained_analyzer_id"],
            "documents": [document_summary(document) for document in reviewed],
        }
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr(
            "analyzer-template.json",
            json.dumps(build_analyzer_resource(project), indent=2),
        )
        for document in reviewed:
            folder = document["role"]
            file_name = document["file_name"]
            archive.write(source_path(project_id, document["document_id"]), f"{folder}/{file_name}")
            archive.writestr(
                f"{folder}/{file_name}.labels.json",
                json.dumps(_labels_payload(document), indent=2),
            )
            result_path = _document_dir(project_id, document["document_id"]) / "result.json"
            if not result_path.is_file():
                raise ValueError(f"{file_name} has no analyzer result to pair with its labels.")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            archive.writestr(
                f"{folder}/{file_name}.result.json",
                json.dumps({"status": "Succeeded", "result": result}, indent=2),
            )
    return f"{project_id}-labeled-data.zip", output.getvalue()


def build_analyzer_resource(
    project: dict[str, Any], *, labeled_data_container_url: str | None = None
) -> dict[str, Any]:
    resource = {
        "baseAnalyzerId": "prebuilt-document",
        "description": f"{project['name']} form field extraction.",
        "config": deepcopy(analyzer_service.load_analyzer_template()["config"]),
        "fieldSchema": deepcopy(project["field_schema"]),
        "models": {"completion": "gpt-5.2", "embedding": "text-embedding-3-large"},
        "tags": {"demo": "local-labeling-workspace", "project": project["project_id"]},
    }
    if labeled_data_container_url:
        analyzer_service._validate_blob_container_url(labeled_data_container_url)
        resource["knowledgeSources"] = [
            {"kind": "labeledData", "containerUrl": labeled_data_container_url}
        ]
    return resource


def _workspace_client():
    from azure.ai.contentunderstanding import ContentUnderstandingClient
    from helpers.azure_credential_utils import get_azure_credential

    endpoint = (
        os.environ.get("APP_CONTENT_UNDERSTANDING_ENDPOINT")
        or os.environ.get("CONTENTUNDERSTANDING_ENDPOINT")
        or os.environ.get("FOUNDRY_ENDPOINT")
    )
    if not endpoint:
        raise RuntimeError("Set APP_CONTENT_UNDERSTANDING_ENDPOINT before using Azure actions.")
    return ContentUnderstandingClient(
        endpoint=endpoint,
        credential=get_azure_credential(),
        api_version=WORKSPACE_API_VERSION,
    )


def _analyze_document(file_bytes: bytes, *, analyzer_id: str) -> dict[str, Any]:
    poller = _workspace_client().begin_analyze_binary(
        analyzer_id=analyzer_id,
        binary_input=file_bytes,
        content_type="application/pdf",
    )
    return analyzer_service._as_dict(poller.result())


def _result_content(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
    return (result.get("contents") or [{}])[0]


def _reviewed_documents(
    project: dict[str, Any], *, role: str
) -> list[dict[str, Any]]:
    documents = []
    for document_id in project["documents"]:
        document = load_document(project["project_id"], document_id)
        if document["role"] == role and document["reviewed"]:
            documents.append(document)
    return documents


def _stage_training_documents(
    project: dict[str, Any], documents: list[dict[str, Any]]
):
    from azure.core.exceptions import ResourceExistsError
    from azure.storage.blob import BlobServiceClient, ContentSettings
    from helpers.azure_credential_utils import get_azure_credential

    account = analyzer_service.storage_account_name()
    container_name = f"cu-label-{project['project_id']}"
    service = BlobServiceClient(
        account_url=f"https://{account}.blob.core.windows.net",
        credential=get_azure_credential(),
    )
    _cleanup_expired_staging_containers(service)
    container = service.get_container_client(container_name)
    try:
        metadata = {
            "project": project["project_id"],
            "expires": str(int((datetime.now(timezone.utc) + timedelta(hours=3)).timestamp())),
        }
        try:
            container.create_container(metadata=metadata)
        except ResourceExistsError:
            container.set_container_metadata(metadata)
        for blob in container.list_blobs():
            container.delete_blob(blob.name)
        for document in documents:
            file_name = document["file_name"]
            container.upload_blob(
                file_name,
                source_path(project["project_id"], document["document_id"]).read_bytes(),
                overwrite=True,
                content_settings=ContentSettings(content_type="application/pdf"),
            )
            container.upload_blob(
                f"{file_name}.labels.json",
                json.dumps(_labels_payload(document)),
                overwrite=True,
                content_settings=ContentSettings(content_type="application/json"),
            )
            raw_result = json.loads(
                (_document_dir(project["project_id"], document["document_id"]) / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            container.upload_blob(
                f"{file_name}.result.json",
                json.dumps({"status": "Succeeded", "result": raw_result}),
                overwrite=True,
                content_settings=ContentSettings(content_type="application/json"),
            )
        return container, f"https://{account}.blob.core.windows.net/{container_name}"
    except Exception:
        try:
            container.delete_container()
        except Exception:
            pass
        raise


def _cleanup_expired_staging_containers(service) -> None:
    now = int(datetime.now(timezone.utc).timestamp())
    for item in service.list_containers(name_starts_with="cu-label-", include_metadata=True):
        metadata = getattr(item, "metadata", None) or {}
        try:
            expired = int(metadata.get("expires", "0")) < now
        except ValueError:
            expired = True
        if expired:
            service.delete_container(item.name)


def _container_sas_url(container_name: str, *, expiry_minutes: int = 120) -> str:
    from azure.storage.blob import (
        BlobServiceClient,
        ContainerSasPermissions,
        generate_container_sas,
    )
    from helpers.azure_credential_utils import get_azure_credential

    account = analyzer_service.storage_account_name()
    service = BlobServiceClient(
        account_url=f"https://{account}.blob.core.windows.net",
        credential=get_azure_credential(),
    )
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=expiry_minutes)
    delegation_key = service.get_user_delegation_key(now - timedelta(minutes=5), expires)
    sas = generate_container_sas(
        account_name=account,
        container_name=container_name,
        user_delegation_key=delegation_key,
        permission=ContainerSasPermissions(read=True, list=True),
        start=now - timedelta(minutes=5),
        expiry=expires,
    )
    return f"https://{account}.blob.core.windows.net/{container_name}?{sas}"


def _is_not_found(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 404 or type(exc).__name__ in {
        "ResourceNotFoundError",
        "NotFoundError",
    }


def _assert_analyzer_ownership(existing: dict[str, Any], project: dict[str, Any]) -> None:
    tags = existing.get("tags") or {}
    if tags.get("demo") != "local-labeling-workspace" or tags.get("project") != project["project_id"]:
        raise ValueError("The Azure analyzer ID is owned by another project and will not be replaced.")


def _assert_unlabeled_document(document: dict[str, Any]) -> None:
    if document.get("status") != "uploaded" or any(
        field.get("value") not in (None, "") for field in document.get("labels", {}).values()
    ):
        raise ValueError(
            "This document already contains labeling work. Upload a new copy instead of replacing reviewed or draft labels."
        )


def _invalidate_evaluation(project: dict[str, Any]) -> None:
    (_project_dir(project["project_id"]) / "evaluation.json").unlink(missing_ok=True)
    project.pop("last_evaluation", None)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _labels_payload(document: dict[str, Any]) -> dict[str, Any]:
    labels = {}
    for field_name, label in document["labels"].items():
        value = label.get("value")
        if value in (None, ""):
            continue
        labels[field_name] = {
            "type": label["type"],
            VALUE_KEYS[label["type"]]: value,
            "kind": label["kind"],
            "source": label.get("source"),
            "spans": label.get("spans") or [],
        }
        if labels[field_name]["source"] is None:
            labels[field_name].pop("source")
    return {
        "$schema": f"https://schema.ai.azure.com/mmi/{analyzer_service.API_VERSION}/labels.json",
        "fileId": document["document_id"],
        "metadata": {"mimeType": "application/pdf"},
        "fieldLabels": labels,
    }


def _result_markdown(result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    payload = result.get("result") if "result" in result else result
    return ((payload.get("contents") or [{}])[0].get("markdown") or "")


def _coerce_value(field_type: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if field_type == "number":
        return float(value)
    if field_type == "integer":
        return int(value)
    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().casefold()
        if normalized not in {"true", "false"}:
            raise ValueError("Boolean labels must be true or false.")
        return normalized == "true"
    return str(value).strip()


def _validate_spans(spans: list[dict[str, Any]], markdown: str) -> list[dict[str, int]]:
    validated = []
    for span in spans:
        offset = span.get("offset")
        length = span.get("length")
        if (
            not isinstance(offset, int)
            or not isinstance(length, int)
            or offset < 0
            or length <= 0
            or offset + length > len(markdown)
        ):
            raise ValueError("Label span is outside the analyzer OCR text.")
        validated.append({"offset": offset, "length": length})
    return validated


def _safe_pdf_name(file_name: str) -> str:
    name = Path(file_name or "").name
    if name != file_name or not name.lower().endswith(".pdf") or len(name) > 160:
        raise ValueError("Each upload must use a plain .pdf filename.")
    return name


def _project_dir(project_id: str) -> Path:
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ValueError("Invalid project ID.")
    return WORKSPACE_ROOT / "projects" / project_id


def _documents_dir(project_id: str) -> Path:
    return _project_dir(project_id) / "documents"


def _document_dir(project_id: str, document_id: str) -> Path:
    if not DOCUMENT_ID_PATTERN.fullmatch(document_id):
        raise ValueError("Invalid document ID.")
    return _documents_dir(project_id) / document_id


def _project_file(project_id: str) -> Path:
    return _project_dir(project_id) / "project.json"


def _document_file(project_id: str, document_id: str) -> Path:
    return _document_dir(project_id, document_id) / "document.json"


def _save_project(project: dict[str, Any]) -> None:
    project["updated_at"] = _utc_now()
    _write_json(_project_file(project["project_id"]), project)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()