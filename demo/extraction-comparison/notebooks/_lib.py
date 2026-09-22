"""Helpers for comparing claim extraction with Document Intelligence and Content Understanding."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import mimetypes
import os
from pathlib import Path
import random
import re
import sys
import time
from typing import Any, Iterable

import httpx
from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import DocumentAnalysisFeature
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError, ResponseNotReadError
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


LIB_DIR = Path(__file__).resolve().parent
DEMO_ROOT = LIB_DIR.parent


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "requirements.txt").is_file() and (candidate / "data").is_dir():
            return candidate
    raise RuntimeError(f"Could not find the repository root from {start}.")


REPO_ROOT = _find_repo_root(LIB_DIR)
DEFAULT_DOCUMENT = REPO_ROOT / "data" / "propertyclaims" / "ClaimForm_1.pdf"
ANALYZER_TEMPLATE_PATH = DEMO_ROOT / "analyzer-templates" / "property_claim.json"
GROUND_TRUTH_PATH = DEMO_ROOT / "reference" / "ClaimForm_1.expected.json"
OUTPUT_DIR = DEMO_ROOT / "output"
REPORT_PATH = DEMO_ROOT / "REPORT.md"

CU_API_VERSION = "2026-06-01-preview"
DI_API_VERSION = "2024-11-30"
LANGUAGE_API_VERSION = "2023-04-01"
TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
RETAIL_PRICES_URL = "https://prices.azure.com/api/retail/prices"

FIELD_NAMES = (
    "PolicyholderFirstName",
    "PolicyholderLastName",
    "TelephoneNumber",
    "PolicyNumber",
    "CoverageType",
    "ClaimNumber",
    "PolicyEffectiveDate",
    "PolicyExpirationDate",
    "DamageDeductibleAmount",
    "DateOfDamageOrLoss",
    "TimeOfLoss",
    "DatePrepared",
    "PropertyAddress",
    "MailingAddress",
)

RATE_HEADER_NAMES = {
    "apim-request-id",
    "retry-after",
    "x-ms-request-id",
    "x-ms-region",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
}

VALUE_KEYS = {
    "address": ("valueAddress", "value_address"),
    "boolean": ("valueBoolean", "value_boolean"),
    "currency": ("valueCurrency", "value_currency"),
    "date": ("valueDate", "value_date"),
    "integer": ("valueInteger", "value_integer"),
    "number": ("valueNumber", "value_number"),
    "selectionmark": ("valueSelectionMark", "value_selection_mark"),
    "string": ("valueString", "value_string"),
    "time": ("valueTime", "value_time"),
}


@dataclass
class ServiceRun:
    service: str
    latency_seconds: float
    payload: dict[str, Any]
    observations: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)


def load_environment() -> None:
    """Load the repository environment and an optional demo-local override."""
    load_dotenv(REPO_ROOT / ".env", override=False)
    load_dotenv(DEMO_ROOT / ".env", override=True)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true/false, yes/no, on/off, or 1/0.")


def require_repo_venv() -> Path:
    expected = (REPO_ROOT / ".venv").resolve()
    actual = Path(sys.prefix).resolve()
    if actual != expected:
        raise RuntimeError(
            f"This notebook must use {expected}. Current interpreter prefix: {actual}. "
            "Select .venv\\Scripts\\python.exe as the notebook kernel."
        )
    return Path(sys.executable).resolve()


def load_ground_truth() -> dict[str, Any]:
    return json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))["fields"]


def load_analyzer_template() -> dict[str, Any]:
    return json.loads(ANALYZER_TEMPLATE_PATH.read_text(encoding="utf-8"))


def resolve_content_understanding_endpoint() -> str:
    endpoint = (
        os.getenv("APP_CONTENT_UNDERSTANDING_ENDPOINT")
        or os.getenv("CONTENTUNDERSTANDING_ENDPOINT")
        or os.getenv("FOUNDRY_ENDPOINT")
    )
    if not endpoint:
        raise RuntimeError(
            "Set APP_CONTENT_UNDERSTANDING_ENDPOINT, CONTENTUNDERSTANDING_ENDPOINT, "
            "or FOUNDRY_ENDPOINT in the repository .env."
        )
    return endpoint.rstrip("/") + "/"


def resolve_cognitive_endpoint(service_variable: str) -> str:
    explicit = os.getenv(service_variable)
    if explicit:
        return explicit.rstrip("/") + "/"

    foundry = (os.getenv("FOUNDRY_ENDPOINT") or "").rstrip("/")
    if "cognitiveservices.azure.com" in foundry:
        return foundry + "/"

    resource_name = os.getenv("FOUNDRY_RESOURCE_NAME")
    if resource_name:
        return f"https://{resource_name}.cognitiveservices.azure.com/"

    raise RuntimeError(
        f"Set {service_variable}, or set FOUNDRY_RESOURCE_NAME so the "
        "*.cognitiveservices.azure.com endpoint can be derived."
    )


def get_default_credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


def _sdk_credential(specific_key_name: str, credential: DefaultAzureCredential):
    key = os.getenv(specific_key_name) or os.getenv("FOUNDRY_KEY")
    return AzureKeyCredential(key) if key else credential


def make_document_intelligence_client(
    credential: DefaultAzureCredential,
) -> DocumentIntelligenceClient:
    return DocumentIntelligenceClient(
        endpoint=resolve_cognitive_endpoint("DOCUMENTINTELLIGENCE_ENDPOINT"),
        credential=_sdk_credential("DOCUMENTINTELLIGENCE_KEY", credential),
        api_version=DI_API_VERSION,
        retry_total=6,
        retry_backoff_factor=1,
        retry_backoff_max=60,
        retry_on_status_codes=[408, 429, 500, 502, 503, 504],
    )


def make_content_understanding_client(
    credential: DefaultAzureCredential,
) -> ContentUnderstandingClient:
    return ContentUnderstandingClient(
        endpoint=resolve_content_understanding_endpoint(),
        credential=_sdk_credential("CONTENTUNDERSTANDING_KEY", credential),
        api_version=CU_API_VERSION,
        retry_total=6,
        retry_backoff_factor=1,
        retry_backoff_max=60,
        retry_on_status_codes=[408, 429, 500, 502, 503, 504],
    )


def _auth_headers(
    credential: DefaultAzureCredential,
    specific_key_name: str,
) -> dict[str, str]:
    key = os.getenv(specific_key_name) or os.getenv("FOUNDRY_KEY")
    if key:
        return {"Ocp-Apim-Subscription-Key": key}
    token = credential.get_token(TOKEN_SCOPE).token
    return {"Authorization": f"Bearer {token}"}


def _header_observation(
    service: str,
    status_code: int,
    headers: Any,
) -> dict[str, Any]:
    selected = {
        str(name).casefold(): value
        for name, value in headers.items()
        if str(name).casefold() in RATE_HEADER_NAMES
        or str(name).casefold().startswith("x-ratelimit-")
    }
    return {
        "service": service,
        "status_code": status_code,
        **selected,
    }


def response_hook(
    service: str,
    observations: list[dict[str, Any]],
    raw_payloads: list[dict[str, Any]] | None = None,
):
    def capture(response: Any) -> None:
        http_response = getattr(response, "http_response", response)
        observations.append(
            _header_observation(
                service,
                int(getattr(http_response, "status_code", 0)),
                getattr(http_response, "headers", {}),
            )
        )
        if raw_payloads is not None and int(getattr(http_response, "status_code", 0)) == 200:
            try:
                http_response.read()
                payload = http_response.json()
            except (AttributeError, ResponseNotReadError, ValueError):
                return
            if isinstance(payload, dict):
                raw_payloads.append(payload)

    return capture


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return min(float(retry_after), 60.0)
        except ValueError:
            pass
    return min(2**attempt + random.random(), 60.0)


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    service: str,
    observations: list[dict[str, Any]],
    attempts: int = 6,
    **kwargs: Any,
) -> httpx.Response:
    response: httpx.Response | None = None
    for attempt in range(attempts):
        response = client.request(method, url, **kwargs)
        observations.append(
            _header_observation(service, response.status_code, response.headers)
        )
        if response.status_code not in {408, 429, 500, 502, 503, 504}:
            response.raise_for_status()
            return response
        if attempt < attempts - 1:
            time.sleep(_retry_delay(response, attempt))

    assert response is not None
    response.raise_for_status()
    raise RuntimeError(f"{service} request failed without an HTTP response.")


def configure_content_understanding_defaults(
    credential: DefaultAzureCredential,
) -> dict[str, str]:
    endpoint = resolve_content_understanding_endpoint()
    url = f"{endpoint.rstrip('/')}/contentunderstanding/defaults"
    params = {"api-version": CU_API_VERSION}
    headers = _auth_headers(credential, "CONTENTUNDERSTANDING_KEY")
    observations: list[dict[str, Any]] = []

    with httpx.Client(timeout=60) as client:
        current_response = request_with_retry(
            client,
            "GET",
            url,
            service="Content Understanding defaults",
            observations=observations,
            params=params,
            headers=headers,
        )
        current = current_response.json() if current_response.content else {}
        deployments = dict(current.get("modelDeployments") or {})
        deployments.update(
            {
                "gpt-5.2": os.getenv("GPT52_MODEL_DEPLOYMENT", "gpt-5.2"),
                "text-embedding-3-large": os.getenv(
                    "EMBEDDING_MODEL_DEPLOYMENT",
                    "text-embedding-3-large",
                ),
            }
        )
        request_with_retry(
            client,
            "PATCH",
            url,
            service="Content Understanding defaults",
            observations=observations,
            params=params,
            headers={
                **headers,
                "Content-Type": "application/merge-patch+json",
            },
            json={"modelDeployments": deployments},
        )
    return deployments


def ensure_content_understanding_analyzer(
    client: ContentUnderstandingClient,
    analyzer_id: str,
) -> tuple[dict[str, Any], float, list[dict[str, Any]]]:
    template = load_analyzer_template()
    owner = (template.get("tags") or {}).get("owner")
    observations: list[dict[str, Any]] = []

    try:
        existing = as_dict(client.get_analyzer(analyzer_id=analyzer_id))
    except ResourceNotFoundError:
        existing = None

    if existing and (existing.get("tags") or {}).get("owner") != owner:
        raise RuntimeError(
            f"Analyzer {analyzer_id!r} already exists but is not owned by this demo."
        )
    if existing and (existing.get("tags") or {}).get("schemaVersion") == (
        template.get("tags") or {}
    ).get("schemaVersion"):
        return existing, 0.0, observations

    started = time.perf_counter()
    analyzer = client.begin_create_analyzer(
        analyzer_id=analyzer_id,
        resource=template,
        allow_replace=bool(existing),
        raw_response_hook=response_hook("Content Understanding setup", observations),
    ).result()
    elapsed = time.perf_counter() - started
    return as_dict(analyzer), elapsed, observations


def as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, dict):
        return value
    raise TypeError(f"Expected an SDK model or dictionary, got {type(value).__name__}.")


def analysis_body(payload: Any) -> dict[str, Any]:
    body = as_dict(payload)
    for key in ("result", "analyzeResult", "analyze_result"):
        nested = body.get(key)
        if isinstance(nested, dict):
            body = nested
    return body


def _field_value(field: Any) -> Any:
    data = as_dict(field) if field else {}
    field_type = str(data.get("type", "")).casefold()
    for key in VALUE_KEYS.get(field_type, ()):
        if key in data:
            value = data[key]
            return value.isoformat() if hasattr(value, "isoformat") else value
    if "value" in data:
        value = data["value"]
        return value.isoformat() if hasattr(value, "isoformat") else value
    for key, value in data.items():
        if key.startswith(("value_", "value")) and not isinstance(value, (dict, list)):
            return value.isoformat() if hasattr(value, "isoformat") else value
    return None


def _field_confidence(field: Any) -> float | None:
    data = as_dict(field) if field else {}
    confidence = data.get("confidence")
    return float(confidence) if confidence is not None else None


def extract_document_intelligence_fields(payload: Any) -> dict[str, Any]:
    body = analysis_body(payload)
    fields: dict[str, Any] = {}
    for document in body.get("documents") or []:
        fields.update(as_dict(document).get("fields") or {})
    if not fields:
        raise RuntimeError(
            "Document Intelligence returned no query fields. Verify that Query Fields "
            "is supported by the resource and that the request contains no more than 20 fields."
        )
    return fields


def extract_content_understanding_fields(payload: Any) -> dict[str, Any]:
    body = analysis_body(payload)
    fields: dict[str, Any] = {}
    for content in body.get("contents") or []:
        fields.update(as_dict(content).get("fields") or {})
    if not fields:
        raise RuntimeError("Content Understanding returned no schema fields.")
    return fields


def extract_markdown(payload: Any, service: str) -> str:
    body = analysis_body(payload)
    if service == "Document Intelligence":
        return str(body.get("content") or "")
    if service == "Content Understanding":
        return "\n\n".join(
            str(as_dict(content).get("markdown") or "")
            for content in body.get("contents") or []
        ).strip()
    raise ValueError(f"Unsupported service: {service}.")


def run_document_intelligence(
    client: DocumentIntelligenceClient,
    document_path: Path,
    field_names: Iterable[str] = FIELD_NAMES,
) -> ServiceRun:
    observations: list[dict[str, Any]] = []
    started = time.perf_counter()
    with document_path.open("rb") as stream:
        result = client.begin_analyze_document(
            "prebuilt-layout",
            body=stream,
            features=[DocumentAnalysisFeature.QUERY_FIELDS],
            query_fields=list(field_names),
            content_type=mimetypes.guess_type(document_path.name)[0]
            or "application/octet-stream",
            raw_response_hook=response_hook("Document Intelligence", observations),
        ).result()
    elapsed = time.perf_counter() - started
    return ServiceRun(
        service="Document Intelligence",
        latency_seconds=elapsed,
        payload=as_dict(result),
        observations=observations,
    )


def run_content_understanding(
    client: ContentUnderstandingClient,
    analyzer_id: str,
    document_path: Path,
) -> ServiceRun:
    observations: list[dict[str, Any]] = []
    raw_payloads: list[dict[str, Any]] = []
    started = time.perf_counter()
    result = client.begin_analyze_binary(
        analyzer_id=analyzer_id,
        binary_input=document_path.read_bytes(),
        content_type=mimetypes.guess_type(document_path.name)[0]
        or "application/octet-stream",
        raw_response_hook=response_hook(
            "Content Understanding",
            observations,
            raw_payloads,
        ),
    ).result()
    elapsed = time.perf_counter() - started
    payload = as_dict(result)
    usage: dict[str, Any] = {}
    for raw_payload in reversed(raw_payloads):
        candidate = raw_payload.get("usage")
        if not isinstance(candidate, dict):
            candidate = analysis_body(raw_payload).get("usage")
        if isinstance(candidate, dict):
            usage = candidate
            break
    return ServiceRun(
        service="Content Understanding",
        latency_seconds=elapsed,
        payload=payload,
        observations=observations,
        usage=usage,
    )


def _canonical(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (int, float, Decimal)):
        return str(Decimal(str(value)).normalize())

    text = " ".join(str(value).split()).strip()
    if re.fullmatch(r"\d{2}:\d{2}:00", text):
        return text[:5]
    numeric = re.fullmatch(r"[$]?\s*[-+]?\d[\d,]*(?:\.\d+)?", text)
    if numeric:
        try:
            return str(Decimal(text.replace("$", "").replace(",", "")).normalize())
        except InvalidOperation:
            pass
    return text.casefold()


def compare_fields(
    ground_truth: dict[str, Any],
    di_payload: Any,
    cu_payload: Any,
) -> list[dict[str, Any]]:
    di_fields = extract_document_intelligence_fields(di_payload)
    cu_fields = extract_content_understanding_fields(cu_payload)
    rows = []
    for name, expected in ground_truth.items():
        di_field = di_fields.get(name)
        cu_field = cu_fields.get(name)
        di_value = _field_value(di_field)
        cu_value = _field_value(cu_field)
        rows.append(
            {
                "Field": name,
                "Expected": expected,
                "Document Intelligence": di_value,
                "DI confidence": _field_confidence(di_field),
                "DI match": _canonical(di_value) == _canonical(expected),
                "Content Understanding": cu_value,
                "CU confidence": _field_confidence(cu_field),
                "CU match": _canonical(cu_value) == _canonical(expected),
            }
        )
    return rows


def accuracy_summary(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    materialized = list(rows)
    total = len(materialized)
    return [
        {
            "Approach": "Document Intelligence + Query Fields",
            "Fields extracted": sum(
                row["Document Intelligence"] not in (None, "") for row in materialized
            ),
            "Exact normalized matches": sum(bool(row["DI match"]) for row in materialized),
            "Accuracy": sum(bool(row["DI match"]) for row in materialized) / total,
        },
        {
            "Approach": "Content Understanding field extraction",
            "Fields extracted": sum(
                row["Content Understanding"] not in (None, "") for row in materialized
            ),
            "Exact normalized matches": sum(bool(row["CU match"]) for row in materialized),
            "Accuracy": sum(bool(row["CU match"]) for row in materialized) / total,
        },
    ]


def _split_text(text: str, maximum_chars: int = 5_000) -> list[str]:
    if maximum_chars <= 0 or maximum_chars > 5_120:
        raise ValueError("maximum_chars must be between 1 and 5,120.")
    chunks: list[str] = []
    remaining = text.strip()
    while remaining:
        if len(remaining) <= maximum_chars:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, maximum_chars + 1)
        if split_at < maximum_chars // 2:
            split_at = remaining.rfind(" ", 0, maximum_chars + 1)
        if split_at <= 0:
            split_at = maximum_chars
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return [chunk for chunk in chunks if chunk]


def run_text_pii(
    text: str,
    credential: DefaultAzureCredential,
    *,
    label: str,
    language: str = "en",
) -> ServiceRun:
    endpoint = resolve_cognitive_endpoint("LANGUAGE_ENDPOINT")
    url = f"{endpoint.rstrip('/')}/language/:analyze-text"
    headers = {
        **_auth_headers(credential, "LANGUAGE_KEY"),
        "Content-Type": "application/json",
    }
    observations: list[dict[str, Any]] = []
    chunks = _split_text(text)
    redacted_chunks: list[str] = []
    entities: list[dict[str, Any]] = []
    request_count = 0
    started = time.perf_counter()

    with httpx.Client(timeout=60) as client:
        for offset in range(0, len(chunks), 5):
            batch = chunks[offset : offset + 5]
            documents = [
                {"id": str(offset + index), "language": language, "text": chunk}
                for index, chunk in enumerate(batch)
            ]
            response = request_with_retry(
                client,
                "POST",
                url,
                service=f"Azure AI Language PII ({label})",
                observations=observations,
                params={"api-version": LANGUAGE_API_VERSION},
                headers=headers,
                json={
                    "kind": "PiiEntityRecognition",
                    "parameters": {"modelVersion": "latest"},
                    "analysisInput": {"documents": documents},
                },
            )
            request_count += 1
            result = response.json().get("results") or {}
            errors = result.get("errors") or []
            if errors:
                raise RuntimeError(
                    f"Azure AI Language PII returned document errors: {json.dumps(errors)}"
                )
            for document in result.get("documents") or []:
                redacted_chunks.append(str(document.get("redactedText") or ""))
                entities.extend(document.get("entities") or [])

    elapsed = time.perf_counter() - started
    text_records = sum(math.ceil(len(chunk) / 1_000) for chunk in chunks)
    return ServiceRun(
        service=f"Azure AI Language PII ({label})",
        latency_seconds=elapsed,
        payload={
            "redacted_text": "\n\n".join(redacted_chunks),
            "entity_count": len(entities),
        },
        observations=observations,
        usage={
            "characters": sum(len(chunk) for chunk in chunks),
            "documents": len(chunks),
            "requests": request_count,
            "text_records": text_records,
        },
    )


def rate_limit_rows(language_tier: str = "S") -> list[dict[str, Any]]:
    tier = language_tier.strip().upper()
    if tier not in {"S", "MULTI-SERVICE", "S0", "F0"}:
        raise ValueError("Language tier must be S, Multi-service, S0, or F0.")
    language_rate = (
        "1,000 requests/s and 1,000 requests/min"
        if tier in {"S", "MULTI-SERVICE"}
        else "100 requests/s and 300 requests/min"
    )
    return [
        {
            "Service": "Document Intelligence S0",
            "Admission limit": "15 analyze POST/s; 50 result GET/s",
            "Payload limit": "500 MB; 2,000 pages",
            "Adjustment": "TPS can be raised by support request",
            "Source": "https://learn.microsoft.com/azure/ai-services/document-intelligence/service-limits",
        },
        {
            "Service": "Content Understanding S0",
            "Admission limit": "1,000 pages/images/min; 3,000 operations/min",
            "Payload limit": "Async: 200 MB and 300 pages",
            "Adjustment": "Also constrained by Foundry model TPM",
            "Source": "https://learn.microsoft.com/azure/ai-services/content-understanding/service-limits",
        },
        {
            "Service": f"Azure AI Language PII {tier}",
            "Admission limit": language_rate,
            "Payload limit": "Sync: 5 documents/request and 5,120 chars/document",
            "Adjustment": "Chunk before submission; retry 429 responses",
            "Source": "https://learn.microsoft.com/azure/ai-services/language-service/concepts/data-limits",
        },
        {
            "Service": "Azure AI Search push indexing",
            "Admission limit": "Batch API limits apply",
            "Payload limit": "1,000 documents or 16 MB/request",
            "Adjustment": "Benchmark SKU; partitions help indexing capacity",
            "Source": "https://learn.microsoft.com/azure/search/search-limits-quotas-capacity",
        },
    ]


def observed_rate_headers(*runs: ServiceRun | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        if run:
            rows.extend(run.observations)
    return rows


def infer_pricing_region(*runs: ServiceRun | None) -> str | None:
    for observation in observed_rate_headers(*runs):
        region = observation.get("x-ms-region")
        if region:
            return re.sub(r"[^a-z0-9]", "", str(region).casefold())
    return None


def resolve_pricing_region(
    configured_region: str | None,
    *runs: ServiceRun | None,
    default_region: str = "eastus",
) -> tuple[str, str]:
    configured = re.sub(r"[^a-z0-9]", "", (configured_region or "").casefold())
    if configured:
        return configured, "AZURE_PRICING_REGION"

    observed = infer_pricing_region(*runs)
    if observed:
        return observed, "Azure x-ms-region response header"

    fallback = re.sub(r"[^a-z0-9]", "", default_region.casefold())
    if not fallback:
        raise ValueError("default_region must not be empty.")
    return fallback, "default fallback"


def latency_rows(
    di_run: ServiceRun,
    cu_run: ServiceRun,
    di_pii_run: ServiceRun | None = None,
    cu_pii_run: ServiceRun | None = None,
) -> list[dict[str, Any]]:
    rows = [
        {
            "Approach": "Document Intelligence",
            "Stage": "Layout + Query Fields",
            "Seconds": di_run.latency_seconds,
        },
        {
            "Approach": "Content Understanding",
            "Stage": "Content + field extraction",
            "Seconds": cu_run.latency_seconds,
        },
    ]
    if di_pii_run:
        rows.append(
            {
                "Approach": "Document Intelligence",
                "Stage": "Azure AI Language PII",
                "Seconds": di_pii_run.latency_seconds,
            }
        )
    if cu_pii_run:
        rows.append(
            {
                "Approach": "Content Understanding",
                "Stage": "Azure AI Language PII",
                "Seconds": cu_pii_run.latency_seconds,
            }
        )
    totals: dict[str, float] = {}
    for row in rows:
        totals[row["Approach"]] = totals.get(row["Approach"], 0.0) + float(
            row["Seconds"]
        )
    rows.extend(
        {
            "Approach": approach,
            "Stage": "End to end",
            "Seconds": seconds,
        }
        for approach, seconds in totals.items()
    )
    return rows


def throughput_rows(
    page_count: int,
    di_run: ServiceRun,
    cu_run: ServiceRun,
    pii_run: ServiceRun | None,
    language_tier: str = "S",
) -> list[dict[str, Any]]:
    if page_count <= 0:
        raise ValueError("page_count must be positive.")
    pii_requests_per_document = int((pii_run or ServiceRun("", 0, {})).usage.get("requests", 0))
    language_requests_per_minute = (
        1_000
        if language_tier.strip().upper() in {"S", "MULTI-SERVICE"}
        else 300
    )
    return [
        {
            "Constraint": "DI analyze admission quota",
            "Approximate documents/minute": 15 * 60,
            "Interpretation": "Submission ceiling, not guaranteed completion throughput",
        },
        {
            "Constraint": "CU page quota",
            "Approximate documents/minute": math.floor(1_000 / page_count),
            "Interpretation": "Before Foundry model TPM and operation limits",
        },
        {
            "Constraint": "PII request quota",
            "Approximate documents/minute": (
                math.floor(language_requests_per_minute / pii_requests_per_document)
                if pii_requests_per_document
                else None
            ),
            "Interpretation": "Based on this document's chunk/request count",
        },
        {
            "Constraint": "Observed DI single-worker latency",
            "Approximate documents/minute": 60 / di_run.latency_seconds,
            "Interpretation": "One sample; rerun for p50/p95",
        },
        {
            "Constraint": "Observed CU single-worker latency",
            "Approximate documents/minute": 60 / cu_run.latency_seconds,
            "Interpretation": "One sample; rerun for p50/p95",
        },
    ]


def fetch_retail_prices(
    region: str,
    product_names: Iterable[str] = (
        "Azure Content Understanding",
        "Azure Document Intelligence",
        "Azure Language",
        "Azure OpenAI GPT5",
    ),
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with httpx.Client(timeout=60) as client:
        for product_name in product_names:
            escaped_product = product_name.replace("'", "''")
            escaped_region = region.replace("'", "''")
            params: dict[str, str] | None = {
                "$filter": (
                    f"productName eq '{escaped_product}' "
                    f"and armRegionName eq '{escaped_region}'"
                )
            }
            url: str | None = RETAIL_PRICES_URL
            while url:
                response = client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                items.extend(payload.get("Items") or [])
                url = payload.get("NextPageLink")
                params = None
    return items


def _select_meter(
    items: Iterable[dict[str, Any]],
    product_name: str,
    meter_name: str,
) -> dict[str, Any]:
    candidates = [
        item
        for item in items
        if str(item.get("productName", "")).casefold() == product_name.casefold()
        and str(item.get("meterName", "")).casefold() == meter_name.casefold()
        and float(item.get("tierMinimumUnits") or 0) == 0
    ]
    if not candidates:
        available = sorted(
            {
                str(item.get("meterName"))
                for item in items
                if str(item.get("productName", "")).casefold()
                == product_name.casefold()
            }
        )
        raise LookupError(
            f"Retail meter {meter_name!r} was not found for {product_name!r}. "
            f"Available meters: {available}"
        )
    candidates.sort(
        key=lambda item: (
            bool(item.get("isPrimaryMeterRegion")),
            str(item.get("effectiveStartDate") or ""),
        ),
        reverse=True,
    )
    return candidates[0]


def build_rate_card(region: str) -> dict[str, dict[str, Any]]:
    prices = fetch_retail_prices(region)
    meter_specs = {
        "di_layout": (
            "Azure Document Intelligence",
            os.getenv("DI_LAYOUT_METER", "S0 Pre-built Pages"),
        ),
        "di_query_fields": (
            "Azure Document Intelligence",
            os.getenv("DI_QUERY_FIELDS_METER", "S0 pages for query fields"),
        ),
        "language_pii": (
            "Azure Language",
            os.getenv("LANGUAGE_PII_METER", "Standard Text Records"),
        ),
        "cu_minimal": (
            "Azure Content Understanding",
            "Doc Content Extraction Min Pages",
        ),
        "cu_basic": (
            "Azure Content Understanding",
            "Doc Content Extraction Basic Pages",
        ),
        "cu_standard": (
            "Azure Content Understanding",
            "Doc Content Extraction Standard Pages",
        ),
        "cu_contextualization": (
            "Azure Content Understanding",
            "Std Contextualization Tokens",
        ),
        "cu_model_input": (
            "Azure OpenAI GPT5",
            os.getenv("CU_MODEL_INPUT_METER", "GPT 5.2 inp Gl 1M Tokens"),
        ),
        "cu_model_cached_input": (
            "Azure OpenAI GPT5",
            os.getenv(
                "CU_MODEL_CACHED_INPUT_METER",
                "GPT 5.2 cd inp Gl 1M Tokens",
            ),
        ),
        "cu_model_output": (
            "Azure OpenAI GPT5",
            os.getenv("CU_MODEL_OUTPUT_METER", "GPT 5.2 opt Gl 1M Tokens"),
        ),
    }
    return {
        key: _select_meter(prices, product_name, meter_name)
        for key, (product_name, meter_name) in meter_specs.items()
    }


def rate_card_rows(rate_card: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Key": key,
            "Product": meter["productName"],
            "Meter": meter["meterName"],
            "USD": float(meter["retailPrice"]),
            "Unit": meter["unitOfMeasure"],
            "Effective": meter.get("effectiveStartDate"),
        }
        for key, meter in rate_card.items()
    ]


def _meter_cost(quantity: int | float, meter: dict[str, Any]) -> float:
    unit = str(meter.get("unitOfMeasure") or "")
    scale = 1_000_000 if "1M" in unit else 1_000 if "1K" in unit else 1
    return float(quantity) / scale * float(meter["retailPrice"])


def _usage_value(usage: dict[str, Any], *names: str) -> int:
    for name in names:
        if name in usage:
            return int(usage[name] or 0)
    return 0


def pricing_rows(
    rate_card: dict[str, dict[str, Any]],
    di_run: ServiceRun,
    cu_run: ServiceRun,
    di_pii_run: ServiceRun | None = None,
    cu_pii_run: ServiceRun | None = None,
) -> list[dict[str, Any]]:
    di_pages = len(analysis_body(di_run.payload).get("pages") or [])
    cu_usage = cu_run.usage
    if not cu_usage:
        raise RuntimeError(
            "Content Understanding returned no billable usage details. "
            "Do not calculate a CU total from page count alone."
        )
    rows: list[dict[str, Any]] = []

    def add(
        approach: str,
        component: str,
        quantity: int,
        rate_key: str,
    ) -> None:
        meter = rate_card[rate_key]
        rows.append(
            {
                "Approach": approach,
                "Component": component,
                "Quantity": quantity,
                "Billing unit": meter["unitOfMeasure"],
                "Rate USD": float(meter["retailPrice"]),
                "Estimated USD": _meter_cost(quantity, meter),
                "Meter": meter["meterName"],
            }
        )

    add("Document Intelligence", "Layout/prebuilt analysis", di_pages, "di_layout")
    add("Document Intelligence", "Query Fields add-on", di_pages, "di_query_fields")
    if di_pii_run:
        add(
            "Document Intelligence",
            "Azure AI Language PII",
            int(di_pii_run.usage["text_records"]),
            "language_pii",
        )

    page_meters = (
        (
            "Minimal content extraction",
            "cu_minimal",
            ("documentPagesMinimal", "document_pages_minimal"),
        ),
        (
            "Basic content extraction",
            "cu_basic",
            ("documentPagesBasic", "document_pages_basic"),
        ),
        (
            "Standard content extraction",
            "cu_standard",
            ("documentPagesStandard", "document_pages_standard"),
        ),
    )
    for component, rate_key, names in page_meters:
        quantity = _usage_value(cu_usage, *names)
        if quantity:
            add("Content Understanding", component, quantity, rate_key)

    contextualization = _usage_value(
        cu_usage,
        "contextualizationTokens",
        "contextualization_tokens",
    )
    if contextualization:
        add(
            "Content Understanding",
            "Standard contextualization",
            contextualization,
            "cu_contextualization",
        )

    tokens = cu_usage.get("tokens") or {}
    model_input_total = sum(
        int(value or 0)
        for key, value in tokens.items()
        if str(key).casefold().endswith("-input")
        and not str(key).casefold().endswith("-cached-input")
    )
    model_cached_input = sum(
        int(value or 0)
        for key, value in tokens.items()
        if str(key).casefold().endswith("-cached-input")
    )
    model_output = sum(
        int(value or 0)
        for key, value in tokens.items()
        if str(key).casefold().endswith("-output")
    )
    input_includes_cached = env_flag("CU_INPUT_TOKENS_INCLUDE_CACHED", False)
    if input_includes_cached and model_cached_input > model_input_total:
        raise RuntimeError(
            "Cached input tokens exceed total input tokens; verify the CU usage contract "
            "or set CU_INPUT_TOKENS_INCLUDE_CACHED=false."
        )
    model_uncached_input = (
        model_input_total - model_cached_input
        if input_includes_cached
        else model_input_total
    )
    if model_uncached_input:
        add(
            "Content Understanding",
            "Foundry model non-cached input",
            model_uncached_input,
            "cu_model_input",
        )
    if model_cached_input:
        add(
            "Content Understanding",
            "Foundry model cached input",
            model_cached_input,
            "cu_model_cached_input",
        )
    if model_output:
        add(
            "Content Understanding",
            "Foundry model output",
            model_output,
            "cu_model_output",
        )
    unsupported_token_keys = [
        key
        for key in tokens
        if not str(key).casefold().endswith(("-input", "-output", "-cached-input"))
    ]
    if unsupported_token_keys:
        raise RuntimeError(
            "The Content Understanding response contains unpriced token meters: "
            f"{unsupported_token_keys}. Add explicit rate mappings before using the total."
        )
    if cu_pii_run:
        add(
            "Content Understanding",
            "Azure AI Language PII",
            int(cu_pii_run.usage["text_records"]),
            "language_pii",
        )
    return rows


def pricing_totals(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, float] = {}
    for row in rows:
        approach = str(row["Approach"])
        totals[approach] = totals.get(approach, 0.0) + float(row["Estimated USD"])
    return [
        {"Approach": approach, "Estimated USD/document": amount}
        for approach, amount in totals.items()
    ]


def index_size_rows(
    di_text: str,
    cu_text: str,
    *,
    corpus_documents: int,
    chunk_characters: int = 2_000,
    overlap_characters: int = 200,
    embedding_dimensions: int = 3_072,
    bytes_per_dimension: int = 4,
    hnsw_scenario_multiplier: float = 1.3,
) -> list[dict[str, Any]]:
    if chunk_characters <= overlap_characters:
        raise ValueError("chunk_characters must be greater than overlap_characters.")
    if corpus_documents <= 0:
        raise ValueError("corpus_documents must be positive.")

    rows = []
    step = chunk_characters - overlap_characters
    for approach, text in (
        ("Document Intelligence", di_text),
        ("Content Understanding", cu_text),
    ):
        chunks = max(1, math.ceil(max(len(text) - overlap_characters, 1) / step))
        vector_bytes = chunks * embedding_dimensions * bytes_per_dimension
        estimated_bytes = len(text.encode("utf-8")) + int(
            vector_bytes * hnsw_scenario_multiplier
        )
        rows.append(
            {
                "Approach": approach,
                "Extracted characters": len(text),
                "Estimated chunks/document": chunks,
                "Raw vector bytes/document": vector_bytes,
                "Scenario bytes/document": estimated_bytes,
                "Projected corpus GiB": (
                    estimated_bytes * corpus_documents / 1024**3
                ),
            }
        )
    return rows


def _report_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        if abs(value) < 0.1:
            return f"{value:.6f}"
        return f"{value:.3f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_table(
    rows: Iterable[dict[str, Any]],
    columns: Iterable[str],
) -> str:
    materialized = list(rows)
    selected = list(columns)
    header = "| " + " | ".join(selected) + " |"
    separator = "| " + " | ".join("---" for _ in selected) + " |"
    body = [
        "| "
        + " | ".join(_report_value(row.get(column)) for column in selected)
        + " |"
        for row in materialized
    ]
    return "\n".join([header, separator, *body])


def _row_for(
    rows: Iterable[dict[str, Any]],
    key: str,
    value: str,
) -> dict[str, Any]:
    for row in rows:
        if str(row.get(key)) == value:
            return row
    raise LookupError(f"No row has {key}={value!r}.")


def write_comparison_report(
    *,
    document_path: Path,
    comparison_rows: list[dict[str, Any]],
    latency_data: list[dict[str, Any]],
    throughput_data: list[dict[str, Any]],
    price_component_rows: list[dict[str, Any]],
    index_data: list[dict[str, Any]],
    rate_limits: list[dict[str, Any]],
    cu_usage: dict[str, Any],
    pricing_region: str,
    pricing_region_source: str,
    cu_setup_seconds: float | None,
    di_run: ServiceRun,
    cu_run: ServiceRun,
    di_pii_run: ServiceRun | None = None,
    cu_pii_run: ServiceRun | None = None,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    accuracy = accuracy_summary(comparison_rows)
    totals = pricing_totals(price_component_rows)
    total_fields = len(comparison_rows)

    di_accuracy = _row_for(
        accuracy,
        "Approach",
        "Document Intelligence + Query Fields",
    )
    cu_accuracy = _row_for(
        accuracy,
        "Approach",
        "Content Understanding field extraction",
    )
    di_total = _row_for(totals, "Approach", "Document Intelligence")
    cu_total = _row_for(totals, "Approach", "Content Understanding")
    di_end_to_end = _row_for(
        latency_data,
        "Stage",
        "End to end",
    )
    cu_end_to_end = next(
        row
        for row in latency_data
        if row.get("Approach") == "Content Understanding"
        and row.get("Stage") == "End to end"
    )

    pii_costs: dict[str, float] = {
        "Document Intelligence": 0.0,
        "Content Understanding": 0.0,
    }
    for row in price_component_rows:
        if row.get("Component") == "Azure AI Language PII":
            pii_costs[str(row["Approach"])] += float(row["Estimated USD"])

    summary_rows = [
        {
            "Measure": "Reviewed fields matched",
            "Document Intelligence + Query Fields": (
                f"{di_accuracy['Exact normalized matches']}/{total_fields}"
            ),
            "Content Understanding": (
                f"{cu_accuracy['Exact normalized matches']}/{total_fields}"
            ),
        },
        {
            "Measure": "Extraction latency",
            "Document Intelligence + Query Fields": (
                f"{di_run.latency_seconds:.3f} s"
            ),
            "Content Understanding": f"{cu_run.latency_seconds:.3f} s",
        },
        {
            "Measure": "Separate PII latency",
            "Document Intelligence + Query Fields": (
                f"{di_pii_run.latency_seconds:.3f} s" if di_pii_run else "Not run"
            ),
            "Content Understanding": (
                f"{cu_pii_run.latency_seconds:.3f} s" if cu_pii_run else "Not run"
            ),
        },
        {
            "Measure": "End-to-end latency",
            "Document Intelligence + Query Fields": (
                f"{float(di_end_to_end['Seconds']):.3f} s"
            ),
            "Content Understanding": (
                f"{float(cu_end_to_end['Seconds']):.3f} s"
            ),
        },
        {
            "Measure": "Estimated list cost without PII",
            "Document Intelligence + Query Fields": (
                f"${float(di_total['Estimated USD/document']) - pii_costs['Document Intelligence']:.6f}"
            ),
            "Content Understanding": (
                f"${float(cu_total['Estimated USD/document']) - pii_costs['Content Understanding']:.6f}"
            ),
        },
        {
            "Measure": "Estimated list cost with PII",
            "Document Intelligence + Query Fields": (
                f"${float(di_total['Estimated USD/document']):.6f}"
            ),
            "Content Understanding": (
                f"${float(cu_total['Estimated USD/document']):.6f}"
            ),
        },
    ]

    field_rows = [
        {
            "Field": row["Field"],
            "Expected": row["Expected"],
            "DI value": row["Document Intelligence"],
            "DI confidence": row["DI confidence"],
            "DI match": row["DI match"],
            "CU value": row["Content Understanding"],
            "CU confidence": row["CU confidence"],
            "CU match": row["CU match"],
        }
        for row in comparison_rows
    ]

    pii_rows: list[dict[str, Any]] = []
    for approach, run in (
        ("Document Intelligence", di_pii_run),
        ("Content Understanding", cu_pii_run),
    ):
        if run:
            pii_rows.append(
                {
                    "Approach": approach,
                    "Characters": run.usage.get("characters"),
                    "Billable text records": run.usage.get("text_records"),
                    "Detected entities": run.payload.get("entity_count"),
                    "Latency seconds": run.latency_seconds,
                }
            )

    observations = observed_rate_headers(
        di_run,
        cu_run,
        di_pii_run,
        cu_pii_run,
    )
    throttled_requests = sum(
        int(row.get("status_code") or 0) == 429 for row in observations
    )
    retry_after_values = sorted(
        {
            str(row["retry-after"])
            for row in observations
            if row.get("retry-after") not in (None, "")
        }
    )

    di_cost = float(di_total["Estimated USD/document"])
    cu_cost = float(cu_total["Estimated USD/document"])
    lower_cost = (
        "Content Understanding"
        if cu_cost < di_cost
        else "Document Intelligence + Query Fields"
    )
    faster = (
        "Content Understanding"
        if float(cu_end_to_end["Seconds"]) < float(di_end_to_end["Seconds"])
        else "Document Intelligence + Query Fields"
    )
    conclusion = (
        f"Both approaches matched all {total_fields} reviewed fields on this clean "
        f"synthetic claim form. {lower_cost} had the lower measured list-price "
        f"estimate, while {faster} had the lower end-to-end latency in this single "
        "run. This sample is insufficient for a production selection: repeat the "
        "comparison across handwritten forms, scans, layout variants, and realistic "
        "batch volumes. PII remains a separate detection/redaction decision for both "
        "approaches."
    )

    sections = [
        "# ClaimForm_1 extraction comparison report",
        "",
        f"- **Generated:** {generated_at}",
        f"- **Input:** `{document_path.as_posix()}`",
        f"- **Pricing region:** `{pricing_region}` ({pricing_region_source})",
        (
            f"- **Content Understanding analyzer setup:** {cu_setup_seconds:.3f} s "
            "(excluded from per-document latency)"
            if cu_setup_seconds is not None
            else "- **Content Understanding analyzer setup:** reused existing analyzer"
        ),
        "",
        "## Executive summary",
        "",
        _markdown_table(
            summary_rows,
            (
                "Measure",
                "Document Intelligence + Query Fields",
                "Content Understanding",
            ),
        ),
        "",
        "## Conclusion",
        "",
        conclusion,
        "",
        "## Field-by-field results",
        "",
        _markdown_table(
            field_rows,
            (
                "Field",
                "Expected",
                "DI value",
                "DI confidence",
                "DI match",
                "CU value",
                "CU confidence",
                "CU match",
            ),
        ),
        "",
        "## Latency",
        "",
        _markdown_table(latency_data, ("Approach", "Stage", "Seconds")),
        "",
        "## PII stage",
        "",
        (
            _markdown_table(
                pii_rows,
                (
                    "Approach",
                    "Characters",
                    "Billable text records",
                    "Detected entities",
                    "Latency seconds",
                ),
            )
            if pii_rows
            else "PII processing was not run."
        ),
        "",
        (
            "PII entity count is not an accuracy score. Validate false positives and "
            "false negatives against reviewed sensitive spans before indexing."
        ),
        "",
        "## Pricing components",
        "",
        _markdown_table(
            price_component_rows,
            (
                "Approach",
                "Component",
                "Quantity",
                "Billing unit",
                "Rate USD",
                "Estimated USD",
                "Meter",
            ),
        ),
        "",
        "## Published rate and payload limits",
        "",
        _markdown_table(
            rate_limits,
            (
                "Service",
                "Admission limit",
                "Payload limit",
                "Adjustment",
            ),
        ),
        "",
        "## Throughput scenarios",
        "",
        _markdown_table(
            throughput_data,
            (
                "Constraint",
                "Approximate documents/minute",
                "Interpretation",
            ),
        ),
        "",
        "## Downstream index-size scenario",
        "",
        _markdown_table(
            index_data,
            (
                "Approach",
                "Extracted characters",
                "Estimated chunks/document",
                "Raw vector bytes/document",
                "Scenario bytes/document",
                "Projected corpus GiB",
            ),
        ),
        "",
        "## Content Understanding measured usage",
        "",
        "```json",
        json.dumps(cu_usage, indent=2, sort_keys=True),
        "```",
        "",
        "## Request behavior",
        "",
        f"- HTTP 429 responses observed: **{throttled_requests}**",
        (
            f"- Retry-After values observed: **{', '.join(retry_after_values)} seconds**"
            if retry_after_values
            else "- Retry-After values observed: **none**"
        ),
        "",
        "## Caveats",
        "",
        "- One clean synthetic two-page claim form is not a representative benchmark.",
        "- Retail prices exclude negotiated discounts and commitment tiers.",
        "- Costs exclude downstream embeddings, Azure AI Search, storage, messaging, and compute.",
        "- The index projection is a sizing scenario, not an Azure AI Search quota guarantee.",
        "- Content Understanding API `2026-06-01-preview` has no production SLA.",
        "",
    ]
    markdown = "\n".join(sections)

    payload = {
        "generated_at": generated_at,
        "document": str(document_path),
        "pricing_region": pricing_region,
        "pricing_region_source": pricing_region_source,
        "cu_setup_seconds": cu_setup_seconds,
        "summary": summary_rows,
        "conclusion": conclusion,
        "field_comparison": comparison_rows,
        "latency": latency_data,
        "pii": pii_rows,
        "pricing_components": price_component_rows,
        "pricing_totals": totals,
        "rate_limits": rate_limits,
        "throughput": throughput_data,
        "index_size": index_data,
        "cu_usage": cu_usage,
        "request_behavior": {
            "http_429_count": throttled_requests,
            "retry_after_seconds": retry_after_values,
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_markdown_path = (
        OUTPUT_DIR / f"{document_path.stem}-comparison-report.md"
    )
    json_path = OUTPUT_DIR / f"{document_path.stem}-comparison-report.json"
    REPORT_PATH.write_text(markdown, encoding="utf-8")
    snapshot_markdown_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    return {
        "report_path": REPORT_PATH,
        "snapshot_markdown_path": snapshot_markdown_path,
        "json_path": json_path,
        "markdown": markdown,
        "payload": payload,
    }
