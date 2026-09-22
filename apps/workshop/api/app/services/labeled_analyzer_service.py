"""Shared evaluation logic for the labeled property-claim analyzer demo."""
from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
from statistics import fmean
from typing import Any, Callable, Iterable, Iterator
from urllib.parse import urlsplit, urlunsplit


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[5]
DEMO_ROOT = Path(
    os.environ.get("LABELED_ANALYZER_DEMO_ROOT")
    or REPO_ROOT / "demo" / "labeled-analyzer"
).resolve()
CLAIMS_DIR = REPO_ROOT / "data" / "propertyclaims"
REFERENCE_DIR = DEMO_ROOT / "reference"
ANALYZER_TEMPLATE_PATH = REFERENCE_DIR / "analyzer-template.json"
GROUND_TRUTH_PATH = REFERENCE_DIR / "ground-truth.json"
LABELED_DATA_DIR = REFERENCE_DIR / "labeled-data"
CU_OUTPUT_DIR = REFERENCE_DIR / "cu-output"
SAMPLE_OUTPUT_DIR = REFERENCE_DIR / "sample-output"
REPORT_PATH = SAMPLE_OUTPUT_DIR / "evaluation-report.json"

API_VERSION = "2025-11-01"
ZERO_SHOT_ANALYZER_ID = "propertyClaimZeroShotGpt52V1"
LABELED_ANALYZER_ID = "propertyClaimLabeledGpt52V1"
STORAGE_CONTAINER = "cu-labeled-claims"
STORAGE_PREFIX = "training/v1/"

TRAINING_FILES = tuple(f"ClaimForm_{index}.pdf" for index in range(1, 6))
HOLDOUT_FILES = (
    "ClaimForm_6.pdf",
    "ClaimForm_7.pdf",
    "claimform_handwritten_1.pdf",
)

FIELD_TYPES = {
    "PolicyholderFirstName": "string",
    "PolicyholderLastName": "string",
    "TelephoneNumber": "string",
    "PolicyNumber": "string",
    "CoverageType": "string",
    "ClaimNumber": "string",
    "PolicyEffectiveDate": "date",
    "PolicyExpirationDate": "date",
    "DamageDeductibleAmount": "number",
    "DateOfDamageOrLoss": "date",
    "TimeOfLoss": "time",
    "DatePrepared": "date",
    "PropertyAddress": "string",
    "MailingAddress": "string",
}

THRESHOLDS = (0.70, 0.80, 0.90, 0.95)

_IDENTIFIER_FIELDS = {"PolicyNumber", "ClaimNumber"}
_ADDRESS_FIELDS = {"PropertyAddress", "MailingAddress"}


def load_ground_truth() -> dict[str, Any]:
    manifest = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    validate_split(manifest["training_files"], manifest["holdout_files"])
    expected_files = set(manifest["training_files"]) | set(manifest["holdout_files"])
    if set(manifest["documents"]) != expected_files:
        raise ValueError("Ground truth documents must exactly match the frozen split.")
    for file_name, document in manifest["documents"].items():
        safe_claim_path(file_name, allowed=expected_files)
        if not document.get("claim_group"):
            raise ValueError(f"Ground truth for {file_name} has no claim_group.")
        missing_fields = set(FIELD_TYPES) - set(document.get("fields", {}))
        if missing_fields:
            raise ValueError(f"Ground truth for {file_name} is missing: {sorted(missing_fields)}")
        null_fields = [name for name, value in document["fields"].items() if value is None]
        if null_fields:
            raise ValueError(f"Ground truth for {file_name} has null values: {null_fields}")
    return manifest


def load_analyzer_template() -> dict[str, Any]:
    template = json.loads(ANALYZER_TEMPLATE_PATH.read_text(encoding="utf-8"))
    fields = template.get("fieldSchema", {}).get("fields", {})
    if {name: definition.get("type") for name, definition in fields.items()} != FIELD_TYPES:
        raise ValueError("Analyzer template fields do not match FIELD_TYPES.")
    return template


def build_analyzer_resource(
    *,
    labeled_data_container_url: str | None = None,
    prefix: str = "training/v1/",
) -> dict[str, Any]:
    resource = deepcopy(load_analyzer_template())
    if labeled_data_container_url:
        _validate_blob_container_url(labeled_data_container_url)
        resource["knowledgeSources"] = [
            {
                "kind": "labeledData",
                "containerUrl": labeled_data_container_url,
                "prefix": prefix,
            }
        ]
    return resource


def assert_analyzer_parity(
    zero_shot: dict[str, Any], labeled: dict[str, Any]
) -> None:
    labeled_without_knowledge = deepcopy(labeled)
    labeled_without_knowledge.pop("knowledgeSources", None)
    if zero_shot != labeled_without_knowledge:
        raise ValueError("A/B analyzer resources differ beyond knowledgeSources.")


def redact_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _validate_blob_container_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc.endswith(".blob.core.windows.net"):
        raise ValueError("Labeled data must use an HTTPS Azure Blob container URL.")
    if len([part for part in parsed.path.split("/") if part]) != 1:
        raise ValueError("containerUrl must identify one Azure Blob container.")


def validate_label_triplets() -> list[dict[str, Path]]:
    triplets: list[dict[str, Path]] = []
    missing: list[str] = []
    for file_name in TRAINING_FILES:
        source = assert_training_file(file_name)
        labels = LABELED_DATA_DIR / f"{file_name}.labels.json"
        result = LABELED_DATA_DIR / f"{file_name}.result.json"
        for path in (labels, result):
            if not path.is_file():
                missing.append(path.name)
        if labels.is_file() and result.is_file():
            result_context = _validate_result_file(file_name, result)
            _validate_labels_file(file_name, labels, result_context)
            triplets.append({"source": source, "labels": labels, "result": result})
    if missing:
        raise FileNotFoundError(f"Missing labeled-data files: {', '.join(sorted(missing))}")
    return triplets


def labeled_data_status() -> dict[str, Any]:
    expected = len(TRAINING_FILES) * 2
    present = sum(
        (LABELED_DATA_DIR / f"{name}{suffix}").is_file()
        for name in TRAINING_FILES
        for suffix in (".labels.json", ".result.json")
    )
    try:
        validate_label_triplets()
        error = None
    except (FileNotFoundError, ValueError) as exc:
        error = str(exc)
    return {
        "ready": error is None,
        "training_documents": len(TRAINING_FILES),
        "sidecars_present": present,
        "sidecars_expected": expected,
        "error": error,
    }


def _validate_labels_file(
    file_name: str, path: Path, result_context: dict[str, Any]
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected_schema = f"https://schema.ai.azure.com/mmi/{API_VERSION}/labels.json"
    if payload.get("$schema") != expected_schema:
        raise ValueError(f"{path.name} must use the {API_VERSION} labels schema.")
    labels = payload.get("fieldLabels") or {}
    if set(labels) != set(FIELD_TYPES):
        raise ValueError(f"{path.name} fields do not match the analyzer schema.")
    metadata = payload.get("metadata") or {}
    if metadata.get("mimeType") not in (None, "application/pdf"):
        raise ValueError(f"{path.name} has the wrong MIME type.")
    markdown = result_context["markdown"]
    page_numbers = result_context["page_numbers"]
    confirmed_span_matches = 0
    for field_name, expected_type in FIELD_TYPES.items():
        label = labels[field_name]
        if label.get("type") != expected_type:
            raise ValueError(f"{path.name}:{field_name} has the wrong type.")
        if label.get("kind") not in {"confirmed", "corrected"}:
            raise ValueError(f"{path.name}:{field_name} must be confirmed or corrected.")
        if content_field_value(label) is None:
            raise ValueError(f"{path.name}:{field_name} has no labeled value.")
        if not label.get("source") and not label.get("spans"):
            raise ValueError(f"{path.name}:{field_name} has no grounding.")
        source_page = _source_page(label.get("source"))
        if source_page is not None and source_page not in page_numbers:
            raise ValueError(f"{path.name}:{field_name} references an unknown page.")
        span_text = _grounded_span_text(markdown, label.get("spans") or [], path.name)
        if label.get("kind") == "confirmed" and span_text:
            if not values_match(field_name, content_field_value(label), span_text):
                raise ValueError(f"{path.name}:{field_name} does not match its OCR span.")
            confirmed_span_matches += 1

    if confirmed_span_matches == 0:
        raise ValueError(f"{path.name} has no confirmed label tied to its OCR result.")

    truth = load_ground_truth()["documents"][file_name]["fields"]
    mismatches = [
        name
        for name, label in labels.items()
        if not values_match(name, truth[name], content_field_value(label))
    ]
    if mismatches:
        raise ValueError(f"{path.name} disagrees with ground truth: {mismatches}")


def _validate_result_file(file_name: str, path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = str(payload.get("status", "")).casefold()
    result = payload.get("result") if "result" in payload else payload
    if status and status != "succeeded":
        raise ValueError(f"{path.name} did not succeed.")
    if not isinstance(result, dict) or not result.get("contents"):
        raise ValueError(f"{path.name} has no Content Understanding result.")
    if result.get("apiVersion") != API_VERSION:
        raise ValueError(f"{path.name} must use Content Understanding {API_VERSION}.")
    content = result["contents"][0]
    markdown = content.get("markdown") or ""
    pages = content.get("pages") or []
    if not markdown.strip() or not pages:
        raise ValueError(f"{path.name} must contain OCR markdown and pages.")
    return {
        "markdown": markdown,
        "page_numbers": {page.get("pageNumber") for page in pages},
    }


def _source_page(source: str | None) -> int | None:
    match = re.match(r"^D\((\d+)", source or "")
    return int(match.group(1)) if match else None


def _grounded_span_text(markdown: str, spans: list[dict[str, Any]], label: str) -> str:
    pieces = []
    for span in spans:
        offset = span.get("offset")
        length = span.get("length")
        if not isinstance(offset, int) or not isinstance(length, int):
            raise ValueError(f"{label} contains an invalid span.")
        if offset < 0 or length <= 0 or offset + length > len(markdown):
            raise ValueError(f"{label} contains an out-of-range span.")
        pieces.append(markdown[offset : offset + length])
    return " ".join(pieces).strip()


def storage_account_name() -> str:
    account = os.environ.get("LABELED_ANALYZER_STORAGE_ACCOUNT") or os.environ.get(
        "STORAGE_ACCOUNT_NAME"
    )
    if not account:
        raise RuntimeError(
            "Set LABELED_ANALYZER_STORAGE_ACCOUNT or STORAGE_ACCOUNT_NAME before uploading labels."
        )
    return account


def storage_container_name() -> str:
    configured = os.environ.get("LABELED_ANALYZER_STORAGE_CONTAINER", STORAGE_CONTAINER)
    if configured != STORAGE_CONTAINER:
        raise ValueError(f"The labeled demo requires its dedicated '{STORAGE_CONTAINER}' container.")
    return configured


def storage_prefix() -> str:
    prefix = os.environ.get("LABELED_ANALYZER_STORAGE_PREFIX", STORAGE_PREFIX).strip("/")
    return f"{prefix}/"


def blob_container_url() -> str:
    return (
        f"https://{storage_account_name()}.blob.core.windows.net/"
        f"{storage_container_name()}"
    )


def _blob_service_client():
    from azure.storage.blob import BlobServiceClient

    from helpers.azure_credential_utils import get_azure_credential

    return BlobServiceClient(
        account_url=f"https://{storage_account_name()}.blob.core.windows.net",
        credential=get_azure_credential(),
    )


def _ensure_blob_container():
    from azure.core.exceptions import ResourceExistsError

    container = _blob_service_client().get_container_client(storage_container_name())
    try:
        container.create_container()
    except ResourceExistsError:
        pass
    return container


def expected_training_blob_names() -> tuple[str, ...]:
    prefix = storage_prefix()
    return tuple(
        f"{prefix}{file_name}{suffix}"
        for file_name in TRAINING_FILES
        for suffix in ("", ".labels.json", ".result.json")
    )


def remote_training_blob_names(container=None) -> tuple[str, ...]:
    container = container or _blob_service_client().get_container_client(
        storage_container_name()
    )
    return tuple(
        sorted(blob.name for blob in container.list_blobs(name_starts_with=storage_prefix()))
    )


def verify_remote_training_inventory(container=None) -> tuple[str, ...]:
    actual = remote_training_blob_names(container)
    expected = expected_training_blob_names()
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        raise ValueError(
            f"Training Blob inventory mismatch; missing={missing}, unexpected={unexpected}"
        )
    return actual


def _clear_training_prefix(container) -> None:
    for blob in container.list_blobs(name_starts_with=storage_prefix()):
        container.delete_blob(blob.name)


def upload_training_sources() -> dict[str, Any]:
    from azure.storage.blob import ContentSettings

    container = _ensure_blob_container()
    _clear_training_prefix(container)
    uploaded = []
    for file_name in TRAINING_FILES:
        source = assert_training_file(file_name)
        blob_name = f"{storage_prefix()}{file_name}"
        with source.open("rb") as stream:
            container.upload_blob(
                name=blob_name,
                data=stream,
                overwrite=True,
                content_settings=ContentSettings(content_type="application/pdf"),
            )
        uploaded.append(blob_name)
    return {
        "container_url": blob_container_url(),
        "prefix": storage_prefix(),
        "uploaded": uploaded,
    }


def download_labeled_sidecars() -> dict[str, Any]:
    container = _blob_service_client().get_container_client(storage_container_name())
    LABELED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = []
    missing = []
    for file_name in TRAINING_FILES:
        for suffix in (".labels.json", ".result.json"):
            blob_name = f"{storage_prefix()}{file_name}{suffix}"
            destination = LABELED_DATA_DIR / f"{file_name}{suffix}"
            try:
                data = container.download_blob(blob_name).readall()
            except Exception as exc:
                if type(exc).__name__ == "ResourceNotFoundError":
                    missing.append(blob_name)
                    continue
                raise
            destination.write_bytes(data)
            downloaded.append(destination.name)
    if missing:
        raise FileNotFoundError(
            "Studio label preparation is incomplete; missing blobs: " + ", ".join(missing)
        )
    validate_label_triplets()
    return {
        "local_directory": str(LABELED_DATA_DIR),
        "downloaded": downloaded,
    }


def sync_labeled_data() -> dict[str, Any]:
    from azure.storage.blob import ContentSettings

    triplets = validate_label_triplets()
    container = _ensure_blob_container()
    _clear_training_prefix(container)

    prefix = storage_prefix()
    uploaded: list[str] = []
    for triplet in triplets:
        for kind, path in triplet.items():
            blob_name = f"{prefix}{path.name}"
            with path.open("rb") as stream:
                container.upload_blob(
                    name=blob_name,
                    data=stream,
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type=(
                            "application/pdf" if kind == "source" else "application/json"
                        )
                    ),
                )
            uploaded.append(blob_name)
    verify_remote_training_inventory(container)
    return {
        "container_url": blob_container_url(),
        "prefix": prefix,
        "uploaded": uploaded,
    }


def create_labeled_data_sas(*, expiry_minutes: int = 60) -> str:
    from azure.storage.blob import (
        BlobServiceClient,
        ContainerSasPermissions,
        generate_container_sas,
    )

    from helpers.azure_credential_utils import get_azure_credential

    if expiry_minutes < 5 or expiry_minutes > 120:
        raise ValueError("SAS expiry must be between 5 and 120 minutes.")
    account = storage_account_name()
    credential = get_azure_credential()
    service = BlobServiceClient(
        account_url=f"https://{account}.blob.core.windows.net",
        credential=credential,
    )
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=5)
    expiry = now + timedelta(minutes=expiry_minutes)
    delegation_key = service.get_user_delegation_key(start, expiry)
    sas = generate_container_sas(
        account_name=account,
        container_name=storage_container_name(),
        user_delegation_key=delegation_key,
        permission=ContainerSasPermissions(read=True, list=True),
        start=start,
        expiry=expiry,
    )
    return f"{blob_container_url()}?{sas}"


@lru_cache(maxsize=1)
def _client():
    from azure.ai.contentunderstanding import ContentUnderstandingClient

    from helpers.azure_credential_utils import get_azure_credential

    endpoint = (
        os.environ.get("APP_CONTENT_UNDERSTANDING_ENDPOINT")
        or os.environ.get("CONTENTUNDERSTANDING_ENDPOINT")
        or os.environ.get("FOUNDRY_ENDPOINT")
    )
    if not endpoint:
        raise RuntimeError("Set APP_CONTENT_UNDERSTANDING_ENDPOINT before using live evaluation.")
    return ContentUnderstandingClient(
        endpoint=endpoint,
        credential=get_azure_credential(),
        api_version=API_VERSION,
    )


def analyzer_status() -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for variant, analyzer_id in (
        ("zero_shot", ZERO_SHOT_ANALYZER_ID),
        ("labeled", LABELED_ANALYZER_ID),
    ):
        try:
            analyzer = _as_dict(_client().get_analyzer(analyzer_id=analyzer_id))
            statuses[variant] = {
                "analyzer_id": analyzer_id,
                "status": analyzer.get("status", "ready"),
                "exists": True,
            }
        except Exception:
            statuses[variant] = {
                "analyzer_id": analyzer_id,
                "status": "missing",
                "exists": False,
            }
    return statuses


def ensure_analyzers(
    *, labeled_data_container_url: str, force_replace: bool = False
) -> dict[str, str]:
    verify_remote_training_inventory()
    zero_shot = build_analyzer_resource()
    labeled = build_analyzer_resource(
        labeled_data_container_url=labeled_data_container_url,
        prefix=storage_prefix(),
    )
    assert_analyzer_parity(zero_shot, labeled)
    resources = {
        ZERO_SHOT_ANALYZER_ID: zero_shot,
        LABELED_ANALYZER_ID: labeled,
    }
    statuses: dict[str, str] = {}
    client = _client()
    for analyzer_id, resource in resources.items():
        if not force_replace:
            try:
                existing = _as_dict(client.get_analyzer(analyzer_id=analyzer_id))
                _validate_existing_analyzer(existing, expected=resource)
                statuses[analyzer_id] = "exists"
                continue
            except ValueError:
                raise
            except Exception:
                pass
        poller = client.begin_create_analyzer(
            analyzer_id=analyzer_id,
            resource=resource,
            allow_replace=force_replace,
        )
        poller.result()
        statuses[analyzer_id] = "replaced" if force_replace else "created"
    return statuses


def _validate_existing_analyzer(
    existing: dict[str, Any], *, expected: dict[str, Any]
) -> None:
    if str(existing.get("status", "ready")).casefold() != "ready":
        raise ValueError("Existing analyzer is not ready.")
    if _canonical_analyzer(existing) != _canonical_analyzer(expected):
        raise ValueError("Existing analyzer does not match the frozen experiment; rebuild it explicitly.")


def _canonical_analyzer(resource: dict[str, Any]) -> dict[str, Any]:
    expected_template = load_analyzer_template()
    canonical = _select_expected_shape(resource, expected_template)
    knowledge = resource.get("knowledgeSources") or []
    if knowledge:
        canonical["knowledgeSources"] = [
            {
                "kind": item.get("kind"),
                "containerUrl": redact_url(item.get("containerUrl", "")),
                "prefix": item.get("prefix"),
                "fileListPath": item.get("fileListPath"),
            }
            for item in knowledge
        ]
    return canonical


def _select_expected_shape(value: Any, expected: Any) -> Any:
    if isinstance(expected, dict):
        actual = value if isinstance(value, dict) else {}
        return {
            key: _select_expected_shape(actual.get(key), expected_value)
            for key, expected_value in expected.items()
        }
    if isinstance(expected, list):
        actual = value if isinstance(value, list) else []
        if not expected:
            return actual
        return [_select_expected_shape(item, expected[0]) for item in actual]
    return value


def analyze_holdout(file_name: str, *, analyzer_id: str) -> dict[str, Any]:
    source = assert_holdout_file(file_name)
    with source.open("rb") as stream:
        poller = _client().begin_analyze_binary(
            analyzer_id=analyzer_id,
            binary_input=stream.read(),
            content_type="application/pdf",
        )
    payload = _as_dict(poller.result())
    _attach_usage(payload, poller)
    return payload


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, dict):
        return value
    return json.loads(json.dumps(value, default=lambda item: getattr(item, "__dict__", str(item))))


def _attach_usage(payload: dict[str, Any], poller: Any) -> None:
    try:
        usage = getattr(poller, "usage", None)
        if usage is not None:
            payload.setdefault("usage", _as_dict(usage))
            return
        response = poller.polling_method()._pipeline_response.http_response
        usage = (response.json() or {}).get("usage")
        if usage:
            payload.setdefault("usage", usage)
    except Exception:
        pass


def project_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from app.services import cost

    if payload.get("cache_version") == 1 and "projection" in payload:
        return payload["projection"]

    content = (payload.get("contents") or [{}])[0]
    fields = content.get("fields") or {}
    projected_fields = {
        field_name: {
            "value": content_field_value(fields.get(field_name)),
            "confidence": (fields.get(field_name) or {}).get("confidence"),
            "source": (fields.get(field_name) or {}).get("source"),
            "spans": (fields.get(field_name) or {}).get("spans") or [],
        }
        for field_name in FIELD_TYPES
    }
    return {
        "analyzer_id": payload.get("analyzerId"),
        "api_version": payload.get("apiVersion"),
        "fields": projected_fields,
        "cost": cost.estimate_cu_cost(payload),
    }


def cache_path(file_name: str, variant: str, repeat: int = 1) -> Path:
    assert_holdout_file(file_name)
    if variant not in {"zero_shot", "labeled"}:
        raise ValueError(f"Unknown analyzer variant: {variant}")
    return CU_OUTPUT_DIR / f"{Path(file_name).stem}.{variant}.run{repeat}.json"


def save_cached_payload(
    file_name: str, variant: str, payload: dict[str, Any], repeat: int = 1
) -> Path:
    path = cache_path(file_name, variant, repeat)
    path.parent.mkdir(parents=True, exist_ok=True)
    cached = {
        "cache_version": 1,
        "projection": project_payload(payload),
    }
    path.write_text(json.dumps(cached, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def load_cached_payload(file_name: str, variant: str, repeat: int = 1) -> dict[str, Any] | None:
    path = cache_path(file_name, variant, repeat)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def evaluate(
    *,
    repeats: int = 1,
    use_cache: bool = True,
    sample_names: Iterable[str] | None = None,
    on_step: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    callback = on_step or (lambda _event: None)
    report = None
    for event_name, data in evaluation_events(
        repeats=repeats,
        use_cache=use_cache,
        sample_names=sample_names,
    ):
        if event_name == "step":
            callback(data)
        else:
            report = data
    if report is None:
        raise RuntimeError("Evaluation did not produce a report.")
    return report


def evaluation_events(
    *,
    repeats: int = 1,
    use_cache: bool = True,
    sample_names: Iterable[str] | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    if repeats < 1 or repeats > 3:
        raise ValueError("repeats must be between 1 and 3")
    selected = resolve_holdouts(sample_names)
    variants = {
        "zero_shot": ZERO_SHOT_ANALYZER_ID,
        "labeled": LABELED_ANALYZER_ID,
    }
    payloads: dict[str, dict[str, list[dict[str, Any]]]] = {
        variant: {} for variant in variants
    }
    for variant, analyzer_id in variants.items():
        for file_name in selected:
            payloads[variant][file_name] = []
            for repeat in range(1, repeats + 1):
                yield (
                    "step",
                    {
                        "step_id": "analyze",
                        "status": "running",
                        "variant": variant,
                        "file_name": file_name,
                        "repeat": repeat,
                    },
                )
                payload = load_cached_payload(file_name, variant, repeat) if use_cache else None
                from_cache = payload is not None
                if payload is None:
                    payload = analyze_holdout(file_name, analyzer_id=analyzer_id)
                    save_cached_payload(file_name, variant, payload, repeat)
                payloads[variant][file_name].append(payload)
                yield (
                    "step",
                    {
                        "step_id": "analyze",
                        "status": "done",
                        "variant": variant,
                        "file_name": file_name,
                        "repeat": repeat,
                        "from_cache": from_cache,
                    },
                )
    yield "step", {"step_id": "score", "status": "running"}
    report = build_report(payloads, repeats=repeats, sample_names=selected)
    if selected == HOLDOUT_FILES:
        save_report(report)
    yield "step", {"step_id": "score", "status": "done"}
    yield "complete", report


def build_report(
    payloads: dict[str, dict[str, list[dict[str, Any]]]],
    *,
    repeats: int,
    sample_names: Iterable[str] | None = None,
) -> dict[str, Any]:
    truth = load_ground_truth()
    selected = resolve_holdouts(sample_names)
    variants: dict[str, Any] = {}
    for variant in ("zero_shot", "labeled"):
        documents: dict[str, Any] = {}
        scores: list[dict[str, Any]] = []
        claim_groups: list[str] = []
        for file_name in selected:
            runs: list[dict[str, Any]] = []
            expected = truth["documents"][file_name]
            for repeat, payload in enumerate(payloads[variant][file_name], start=1):
                projected = project_payload(payload)
                score = score_document(expected["fields"], projected["fields"])
                scores.append(score)
                claim_groups.append(expected["claim_group"])
                runs.append({"repeat": repeat, "result": projected, "score": score})
            documents[file_name] = {
                "challenge": expected["challenge"],
                "claim_group": expected["claim_group"],
                "runs": runs,
            }
        variants[variant] = {
            "analyzer_id": (
                ZERO_SHOT_ANALYZER_ID if variant == "zero_shot" else LABELED_ANALYZER_ID
            ),
            "documents": documents,
            "aggregate": aggregate_scores(scores, claim_groups=claim_groups),
        }

    zero = variants["zero_shot"]["aggregate"]
    labeled = variants["labeled"]["aggregate"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_version": API_VERSION,
        "model": "gpt-5.2",
        "embedding_model": "text-embedding-3-large",
        "training_files": list(TRAINING_FILES),
        "training_unique_claims": len(
            {
                truth["documents"][file_name]["claim_group"]
                for file_name in TRAINING_FILES
            }
        ),
        "holdout_files": list(selected),
        "holdout_unique_claims": len(
            {truth["documents"][file_name]["claim_group"] for file_name in selected}
        ),
        "repeats": repeats,
        "experiment_fingerprint": experiment_fingerprint(selected),
        "variants": variants,
        "summary": {
            "zero_shot_accuracy": zero["accuracy"],
            "labeled_accuracy": labeled["accuracy"],
            "accuracy_delta_points": (labeled["accuracy"] - zero["accuracy"]) * 100,
            "zero_shot_false_accepts_at_090": zero["thresholds"]["0.90"]["false_accepts"],
            "labeled_false_accepts_at_090": labeled["thresholds"]["0.90"]["false_accepts"],
        },
    }


def aggregate_scores(
    scores: Iterable[dict[str, Any]], *, claim_groups: Iterable[str] | None = None
) -> dict[str, Any]:
    score_list = list(scores)
    group_list = list(claim_groups or [str(index) for index in range(len(score_list))])
    if len(group_list) != len(score_list):
        raise ValueError("Each score must have one claim group.")
    rows = [row for score in score_list for row in score["fields"]]
    total = len(rows)
    correct = sum(row["correct"] for row in rows)
    missing = sum(row["missing"] for row in rows)
    correct_confidences = [float(row["confidence"]) for row in rows if row["correct"] and row["confidence"] is not None]
    incorrect_confidences = [float(row["confidence"]) for row in rows if not row["correct"] and row["confidence"] is not None]
    thresholds: dict[str, Any] = {}
    for threshold in THRESHOLDS:
        accepted = [row for row in rows if row["confidence"] is not None and float(row["confidence"]) >= threshold]
        false_accepts = sum(not row["correct"] for row in accepted)
        thresholds[f"{threshold:.2f}"] = {
            "accepted": len(accepted),
            "false_accepts": false_accepts,
            "coverage": len(accepted) / total if total else 0.0,
            "precision": ((len(accepted) - false_accepts) / len(accepted) if accepted else None),
        }
    field_accuracy = {}
    for field_name in FIELD_TYPES:
        field_rows = [row for row in rows if row["field_name"] == field_name]
        field_accuracy[field_name] = sum(row["correct"] for row in field_rows) / len(field_rows) if field_rows else 0.0
    rows_by_group: dict[str, list[dict[str, Any]]] = {}
    for group, score in zip(group_list, score_list):
        rows_by_group.setdefault(group, []).extend(score["fields"])
    grouped_accuracies = [
        sum(row["correct"] for row in group_rows) / len(group_rows)
        for group_rows in rows_by_group.values()
        if group_rows
    ]
    document_weighted_accuracy = correct / total if total else 0.0
    grouped_accuracy = fmean(grouped_accuracies) if grouped_accuracies else 0.0
    return {
        "total_fields": total,
        "correct_fields": correct,
        "missing_fields": missing,
        "accuracy": grouped_accuracy,
        "grouped_accuracy": grouped_accuracy,
        "document_weighted_accuracy": document_weighted_accuracy,
        "unique_claims": len(rows_by_group),
        "missing_rate": missing / total if total else 0.0,
        "mean_confidence_correct": fmean(correct_confidences) if correct_confidences else None,
        "mean_confidence_incorrect": fmean(incorrect_confidences) if incorrect_confidences else None,
        "thresholds": thresholds,
        "field_accuracy": field_accuracy,
    }


def save_report(report: dict[str, Any]) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    return REPORT_PATH


def load_report() -> dict[str, Any] | None:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8")) if REPORT_PATH.is_file() else None


def load_valid_report() -> dict[str, Any] | None:
    report = load_report()
    if report is None:
        return None
    validate_cached_report(
        report,
        sample_names=HOLDOUT_FILES,
        repeats=report.get("repeats", 0),
    )
    return report


def experiment_fingerprint(sample_names: Iterable[str] | None = None) -> dict[str, Any]:
    selected = resolve_holdouts(sample_names)
    components = {
        "template": _sha256_file(ANALYZER_TEMPLATE_PATH),
        "ground_truth": _sha256_file(GROUND_TRUTH_PATH),
        "sources": {name: _sha256_file(assert_holdout_file(name)) for name in selected},
        "labeled_data": {
            path.name: _sha256_file(path)
            for path in sorted(LABELED_DATA_DIR.glob("*.json"))
        },
        "api_version": API_VERSION,
        "model": "gpt-5.2",
        "embedding_model": "text-embedding-3-large",
        "analyzer_ids": [ZERO_SHOT_ANALYZER_ID, LABELED_ANALYZER_ID],
    }
    digest = hashlib.sha256(
        json.dumps(components, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"digest": digest, "components": components}


def validate_cached_report(
    report: dict[str, Any], *, sample_names: Iterable[str], repeats: int
) -> None:
    selected = resolve_holdouts(sample_names)
    if tuple(report.get("holdout_files", [])) != selected or report.get("repeats") != repeats:
        raise ValueError("The cached report does not match the selected samples and repeat count.")
    current = experiment_fingerprint(selected)
    if report.get("experiment_fingerprint", {}).get("digest") != current["digest"]:
        raise ValueError("The cached report is stale for the current schema, truth, labels, or PDFs.")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_split(
    training_files: Iterable[str] = TRAINING_FILES,
    holdout_files: Iterable[str] = HOLDOUT_FILES,
) -> None:
    training = set(training_files)
    holdout = set(holdout_files)
    if not training or not holdout:
        raise ValueError("Training and holdout sets must both be nonempty.")
    overlap = sorted(training & holdout)
    if overlap:
        raise ValueError(f"Training and holdout sets overlap: {overlap}")


def safe_claim_path(file_name: str, *, allowed: Iterable[str]) -> Path:
    if not file_name or Path(file_name).name != file_name:
        raise ValueError("A plain claim PDF filename is required.")
    if file_name not in set(allowed):
        raise ValueError(f"File is not part of this demo set: {file_name}")
    path = (CLAIMS_DIR / file_name).resolve()
    if path.parent != CLAIMS_DIR.resolve() or not path.is_file():
        raise FileNotFoundError(file_name)
    return path


def assert_training_file(file_name: str) -> Path:
    return safe_claim_path(file_name, allowed=TRAINING_FILES)


def assert_holdout_file(file_name: str) -> Path:
    return safe_claim_path(file_name, allowed=HOLDOUT_FILES)


def resolve_holdouts(sample_names: Iterable[str] | None = None) -> tuple[str, ...]:
    selected = tuple(sample_names) if sample_names is not None else HOLDOUT_FILES
    if not selected:
        raise ValueError("Select at least one held-out sample.")
    if len(set(selected)) != len(selected):
        raise ValueError("Held-out sample names must be unique.")
    for file_name in selected:
        assert_holdout_file(file_name)
    return selected


def content_field_value(field: dict[str, Any] | None) -> Any:
    if not field:
        return None
    field_type = field.get("type")
    key = {
        "string": "valueString",
        "date": "valueDate",
        "time": "valueTime",
        "number": "valueNumber",
        "integer": "valueInteger",
        "boolean": "valueBoolean",
    }.get(field_type)
    return field.get(key) if key else None


def normalize_value(field_name: str, value: Any) -> Any:
    if value is None:
        return None
    field_type = FIELD_TYPES[field_name]
    text = unicodedata.normalize("NFKC", str(value)).strip()
    if not text:
        return None

    if field_type == "number":
        try:
            return Decimal(re.sub(r"[^0-9+\-.]", "", text))
        except InvalidOperation:
            return text.casefold()

    if field_type == "date":
        return _normalize_date(text)

    if field_type == "time":
        return _normalize_time(text)

    if field_name == "TelephoneNumber":
        return re.sub(r"\D", "", text)

    if field_name in _IDENTIFIER_FIELDS:
        return re.sub(r"[^a-z0-9]", "", text.casefold())

    normalized = re.sub(r"\s+", " ", text).casefold()
    if field_name in _ADDRESS_FIELDS:
        normalized = re.sub(r"[,.]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _normalize_date(value: str) -> date | str:
    for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    return value.casefold()


def _normalize_time(value: str) -> time | str:
    for pattern in ("%H:%M:%S", "%H:%M", "%I:%M %p"):
        try:
            return datetime.strptime(value, pattern).time()
        except ValueError:
            continue
    return value.casefold()


def values_match(field_name: str, expected: Any, actual: Any) -> bool:
    return normalize_value(field_name, expected) == normalize_value(field_name, actual)


def score_document(
    expected: dict[str, Any],
    predicted: dict[str, dict[str, Any]],
    *,
    thresholds: Iterable[float] = THRESHOLDS,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for field_name in FIELD_TYPES:
        prediction = predicted.get(field_name) or {}
        actual = prediction.get("value")
        confidence = prediction.get("confidence")
        correct = values_match(field_name, expected.get(field_name), actual)
        rows.append(
            {
                "field_name": field_name,
                "expected": expected.get(field_name),
                "actual": actual,
                "confidence": confidence,
                "correct": correct,
                "missing": actual is None,
                "source": prediction.get("source"),
                "spans": prediction.get("spans") or [],
            }
        )

    total = len(rows)
    correct_count = sum(row["correct"] for row in rows)
    missing_count = sum(row["missing"] for row in rows)
    threshold_metrics: dict[str, dict[str, Any]] = {}
    for threshold in thresholds:
        accepted = [
            row
            for row in rows
            if row["confidence"] is not None and float(row["confidence"]) >= threshold
        ]
        false_accepts = sum(not row["correct"] for row in accepted)
        threshold_metrics[f"{threshold:.2f}"] = {
            "accepted": len(accepted),
            "false_accepts": false_accepts,
            "coverage": len(accepted) / total if total else 0.0,
            "precision": (
                (len(accepted) - false_accepts) / len(accepted) if accepted else None
            ),
        }

    return {
        "fields": rows,
        "total_fields": total,
        "correct_fields": correct_count,
        "missing_fields": missing_count,
        "accuracy": correct_count / total if total else 0.0,
        "missing_rate": missing_count / total if total else 0.0,
        "thresholds": threshold_metrics,
    }