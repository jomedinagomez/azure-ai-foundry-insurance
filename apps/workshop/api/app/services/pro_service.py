"""Pro Mode Content Understanding service.

Calls the Azure Content Understanding **pro mode** REST API directly
(`api-version=2025-05-01-preview`) via `httpx`, rather than going through
the `azure-ai-contentunderstanding` Python SDK. We do this because:

1. Pro mode is **preview-only** and the SDK's multi-input / reference-data
   surface area is still evolving across versions.
2. The REST shape is well-documented and stable for the preview API.
3. Going direct keeps the SOV / SEC standard-mode SDK usage cleanly
   separated from the pro-mode preview surface.

Authentication uses `DefaultAzureCredential` (matching the rest of the
workshop API). The bearer token scope is the Cognitive Services scope.

See: https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/standard-pro-modes
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx

from helpers.azure_credential_utils import get_azure_credential
from app.schemas.pro import (
    FraudSignal,
    ProClaimsFields,
    ProClaimsResult,
    ProFraudFields,
    ProFraudResult,
    ProMeta,
    ProSampleManifest,
)
from app.services import fraud_rules

# ── Paths / config ──────────────────────────────────────────────────────────
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[5]
PRO_DEMO_ROOT = Path(
    os.environ.get("PRO_DEMO_ROOT")
    or (REPO_ROOT / "demo" / "pro")
).resolve()
TEMPLATE_DIR = PRO_DEMO_ROOT / "analyzer-templates"
SAMPLES_DIR = PRO_DEMO_ROOT / "samples"
REFERENCE_DATA_DIR = PRO_DEMO_ROOT / "reference-data"
CU_OUTPUT_DIR = PRO_DEMO_ROOT / "reference" / "cu-output"

API_VERSION = "2025-05-01-preview"
ANALYZER_CLAIMS_ID = "proClaimsV1"
ANALYZER_FRAUD_ID = "proFraudV1"
CLAIMS_TEMPLATE = "pro_claims.json"
FRAUD_TEMPLATE = "pro_fraud.json"
SCOPE = "https://cognitiveservices.azure.com/.default"

POLL_INTERVAL_SEC = 2.0
POLL_TIMEOUT_SEC = 180.0


def _endpoint() -> str:
    ep = (
        os.environ.get("APP_CONTENT_UNDERSTANDING_ENDPOINT")
        or os.environ.get("CONTENTUNDERSTANDING_ENDPOINT")
        or os.environ.get("FOUNDRY_ENDPOINT")
    )
    if not ep:
        raise RuntimeError(
            "Pro mode: set APP_CONTENT_UNDERSTANDING_ENDPOINT (or "
            "CONTENTUNDERSTANDING_ENDPOINT / FOUNDRY_ENDPOINT) in the env."
        )
    return ep.rstrip("/")


# ── Auth ────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _credential():
    return get_azure_credential()


def _bearer() -> str:
    token = _credential().get_token(SCOPE)
    return f"Bearer {token.token}"


def _headers(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    h = {
        "Authorization": _bearer(),
        "x-ms-useragent": "azure-ai-foundry-insurance-workshop/pro-mode",
    }
    if extra:
        h.update(extra)
    return h


# ── Template loading ────────────────────────────────────────────────────────
@lru_cache(maxsize=4)
def _raw_template(name: str) -> dict[str, Any]:
    return json.loads((TEMPLATE_DIR / name).read_text(encoding="utf-8"))


def _inject_models(tmpl: dict[str, Any]) -> None:
    """Wire a `models` block into a pro-mode analyzer template, mirroring
    the standard-mode SEC service. Pro mode requires a chat-completion model
    deployment for the multi-step reasoning step.

    Resolution order (first non-empty wins):
      1. APP_CU_PRO_COMPLETION_DEPLOYMENT   (preferred — pro-mode specific)
      2. APP_CU_COMPLETION_DEPLOYMENT       (shared with SEC)
      3. GPT52_MODEL_DEPLOYMENT             (GPT-5.2 deployment name)
      4. GPT51_MODEL_DEPLOYMENT             (fallback)
      5. GPT41_MODEL_DEPLOYMENT             (legacy fallback)
    """
    completion = (
        os.environ.get("APP_CU_PRO_COMPLETION_DEPLOYMENT")
        or os.environ.get("APP_CU_COMPLETION_DEPLOYMENT")
        or os.environ.get("GPT52_MODEL_DEPLOYMENT")
        or os.environ.get("GPT51_MODEL_DEPLOYMENT")
        or os.environ.get("GPT41_MODEL_DEPLOYMENT")
    )
    if completion:
        tmpl.setdefault("models", {})["completion"] = completion


def _template(name: str) -> dict[str, Any]:
    """Load a pro-mode template and inject env-configured model deployments."""
    tmpl = dict(_raw_template(name))  # shallow copy so model injection isn't cached
    _inject_models(tmpl)
    return tmpl


# ── Samples ─────────────────────────────────────────────────────────────────
def list_sample_manifests() -> list[ProSampleManifest]:
    manifests: list[ProSampleManifest] = []
    if not SAMPLES_DIR.exists():
        return manifests
    for child in sorted(SAMPLES_DIR.iterdir()):
        m = child / "manifest.json"
        if not m.exists():
            continue
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
            manifests.append(ProSampleManifest(**data))
        except Exception:
            # Don't crash listing on a single bad manifest.
            continue
    return manifests


def load_sample(sample_id: str) -> tuple[ProSampleManifest, list[Path]]:
    folder = SAMPLES_DIR / sample_id
    m = folder / "manifest.json"
    if not folder.exists() or not m.exists():
        raise FileNotFoundError(f"Sample not found: {sample_id}")
    manifest = ProSampleManifest(**json.loads(m.read_text(encoding="utf-8")))
    files = [folder / f.name for f in manifest.files]
    missing = [str(p) for p in files if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing files for sample {sample_id}: {missing}")
    return manifest, files


# ── Analyzer deploy ─────────────────────────────────────────────────────────
def _analyzer_url(analyzer_id: str) -> str:
    return (
        f"{_endpoint()}/contentunderstanding/analyzers/"
        f"{analyzer_id}?api-version={API_VERSION}"
    )


def analyzer_exists(analyzer_id: str, *, client: Optional[httpx.Client] = None) -> bool:
    own = client is None
    c = client or httpx.Client(timeout=30.0)
    try:
        r = c.get(_analyzer_url(analyzer_id), headers=_headers())
        return r.status_code == 200
    finally:
        if own:
            c.close()


def _build_resource(
    template_name: str,
    *,
    reference_files: Optional[list[Path]] = None,
) -> dict[str, Any]:
    """Construct the analyzer-create body. Reference files (e.g. the policy
    PDF) are inlined as base64 under `referenceData`."""
    resource = dict(_template(template_name))
    if reference_files:
        refs = []
        for p in reference_files:
            refs.append({
                "fileName": p.name,
                "data": base64.b64encode(p.read_bytes()).decode("ascii"),
                "mediaType": _media_type(p),
            })
        resource["referenceData"] = {"files": refs}
    return resource


def deploy_analyzer(
    analyzer_id: str,
    template_name: str,
    *,
    reference_files: Optional[list[Path]] = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create the named pro-mode analyzer. No-op if it already exists
    (unless `overwrite=True`)."""
    with httpx.Client(timeout=300.0) as client:
        if analyzer_exists(analyzer_id, client=client):
            if not overwrite:
                return {"status": "exists", "analyzer_id": analyzer_id}
            client.delete(_analyzer_url(analyzer_id), headers=_headers())

        body = _build_resource(template_name, reference_files=reference_files)
        r = client.put(
            _analyzer_url(analyzer_id),
            headers=_headers({"Content-Type": "application/json"}),
            content=json.dumps(body),
        )
        if r.status_code >= 400:
            raise RuntimeError(
                f"Failed to create analyzer {analyzer_id}: "
                f"HTTP {r.status_code} {r.text[:500]}"
            )
        # PUT may return 201 + operation-location; poll if so.
        op_loc = r.headers.get("operation-location")
        if op_loc:
            _poll_operation(client, op_loc)
        return {"status": "created", "analyzer_id": analyzer_id}


def delete_analyzer(analyzer_id: str) -> None:
    with httpx.Client(timeout=60.0) as client:
        client.delete(_analyzer_url(analyzer_id), headers=_headers())


def deploy_all(*, overwrite: bool = False) -> dict[str, Any]:
    """Deploy both pro-mode analyzers with auto_policy.pdf as reference data."""
    policy_pdf = REFERENCE_DATA_DIR / "auto_policy.pdf"
    if not policy_pdf.exists():
        raise FileNotFoundError(
            f"Reference policy missing: {policy_pdf}. "
            f"Run `python demo/pro/scripts/generate_policy.py`."
        )
    refs = [policy_pdf]
    return {
        ANALYZER_CLAIMS_ID: deploy_analyzer(
            ANALYZER_CLAIMS_ID, CLAIMS_TEMPLATE,
            reference_files=refs, overwrite=overwrite,
        ),
        ANALYZER_FRAUD_ID: deploy_analyzer(
            ANALYZER_FRAUD_ID, FRAUD_TEMPLATE,
            reference_files=refs, overwrite=overwrite,
        ),
    }


# ── Analyze (multi-input pro mode) ──────────────────────────────────────────
_MEDIA_BY_EXT = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def _media_type(p: Path) -> str:
    return _MEDIA_BY_EXT.get(p.suffix.lower(), "application/octet-stream")


def _analyze_url(analyzer_id: str) -> str:
    return (
        f"{_endpoint()}/contentunderstanding/analyzers/"
        f"{analyzer_id}:analyze?api-version={API_VERSION}"
    )


def _poll_operation(client: httpx.Client, op_location: str) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SEC
    while True:
        r = client.get(op_location, headers=_headers())
        if r.status_code >= 400:
            raise RuntimeError(f"Polling failed: HTTP {r.status_code} {r.text[:500]}")
        body = r.json() if r.content else {}
        status = (body.get("status") or "").lower()
        if status in ("succeeded", "failed", "cancelled", "canceled"):
            if status != "succeeded":
                raise RuntimeError(f"Operation {status}: {json.dumps(body)[:500]}")
            return body
        if time.monotonic() > deadline:
            raise TimeoutError(f"Operation timed out after {POLL_TIMEOUT_SEC}s")
        time.sleep(POLL_INTERVAL_SEC)


def analyze_multi(analyzer_id: str, files: list[Path]) -> dict[str, Any]:
    """Submit multiple files to a pro-mode analyzer's :analyze endpoint and
    return the parsed JSON result."""
    inputs = []
    for p in files:
        inputs.append({
            "fileName": p.name,
            "data": base64.b64encode(p.read_bytes()).decode("ascii"),
            "mediaType": _media_type(p),
        })
    body = {"inputs": inputs}
    with httpx.Client(timeout=300.0) as client:
        r = client.post(
            _analyze_url(analyzer_id),
            headers=_headers({"Content-Type": "application/json"}),
            content=json.dumps(body),
        )
        if r.status_code >= 400:
            raise RuntimeError(
                f"analyze {analyzer_id} failed: HTTP {r.status_code} {r.text[:500]}"
            )
        if r.status_code == 200 and r.content:
            return r.json()
        op_loc = r.headers.get("operation-location")
        if not op_loc:
            raise RuntimeError(
                f"analyze {analyzer_id}: no operation-location and no body "
                f"(HTTP {r.status_code})"
            )
        return _poll_operation(client, op_loc)


# ── Field projection ────────────────────────────────────────────────────────
_FIELD_KEYS = ("valueString", "valueNumber", "valueInteger", "valueDate",
               "valueBoolean", "valueArray", "valueObject")


def _unwrap_field(field: Any) -> Any:
    if not isinstance(field, dict):
        return field
    for k in _FIELD_KEYS:
        if k in field and field[k] is not None:
            return field[k]
    return None


def _first_content_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """Pro mode returns `result.contents[0].fields` (analogous to standard).
    We tolerate both shapes."""
    # Drill into common envelope variants
    result = raw.get("result") if isinstance(raw.get("result"), dict) else raw
    contents = result.get("contents") or []
    if contents:
        return contents[0].get("fields") or {}
    # Some preview variants return `fields` at the top level
    return result.get("fields") or raw.get("fields") or {}


def project_claims_fields(raw: dict[str, Any]) -> ProClaimsFields:
    f = _first_content_fields(raw)
    return ProClaimsFields(
        claimant_name=_unwrap_field(f.get("ClaimantName")),
        policy_number=_unwrap_field(f.get("PolicyNumber")),
        vin=_unwrap_field(f.get("VIN")),
        date_of_loss=_unwrap_field(f.get("DateOfLoss")),
        loss_location=_unwrap_field(f.get("LossLocation")),
        incident_narrative=_unwrap_field(f.get("IncidentNarrative")),
        estimated_total=_unwrap_field(f.get("EstimatedTotal")),
        damage_visible_in_photo=_unwrap_field(f.get("DamageVisibleInPhoto")),
        coverage_applies=_unwrap_field(f.get("CoverageApplies")),
        police_report_present=_unwrap_field(f.get("PoliceReportPresent")),
        document_set_completeness=_unwrap_field(f.get("DocumentSetCompleteness")),
        claims_handler_verdict=_unwrap_field(f.get("ClaimsHandlerVerdict")),
    )


def project_fraud_fields(raw: dict[str, Any]) -> ProFraudFields:
    f = _first_content_fields(raw)
    return ProFraudFields(
        vin_consistency=_unwrap_field(f.get("VinConsistency")),
        vin_consistency_evidence=_unwrap_field(f.get("VinConsistencyEvidence")),
        policy_number_consistency=_unwrap_field(f.get("PolicyNumberConsistency")),
        claimant_name_consistency=_unwrap_field(f.get("ClaimantNameConsistency")),
        totals_vs_sub_limit=_unwrap_field(f.get("TotalsVsSubLimit")),
        totals_evidence=_unwrap_field(f.get("TotalsEvidence")),
        estimate_date_vs_date_of_loss=_unwrap_field(f.get("EstimateDateVsDateOfLoss")),
        date_evidence=_unwrap_field(f.get("DateEvidence")),
        narrative_image_consistency=_unwrap_field(f.get("NarrativeImageConsistency")),
        narrative_image_evidence=_unwrap_field(f.get("NarrativeImageEvidence")),
        overall_fraud_indication=_unwrap_field(f.get("OverallFraudIndication")),
        rationale=_unwrap_field(f.get("Rationale")),
    )


# ── CU signal extraction (maps fraud-analyzer classify outputs to signals) ──
_CU_SIGNAL_MAP = {
    # field name -> (rule_id, severity, title, weight, bad_values)
    "vin_consistency": (
        "CU_VIN_MISMATCH", "medium",
        "CU reasoning flagged a VIN mismatch", 20, {"Mismatch"},
    ),
    "policy_number_consistency": (
        "CU_POLICY_NUMBER_MISMATCH", "medium",
        "CU reasoning flagged a policy-number mismatch", 18, {"Mismatch"},
    ),
    "claimant_name_consistency": (
        "CU_NAME_MISMATCH", "medium",
        "CU reasoning flagged a claimant-name mismatch", 15, {"Mismatch"},
    ),
    "totals_vs_sub_limit": (
        "CU_TOTALS_EXCEED_SUBLIMIT", "high",
        "CU reasoning flagged repair total over policy sub-limit", 25,
        {"ExceedsCollisionSubLimit"},
    ),
    "estimate_date_vs_date_of_loss": (
        "CU_DATE_BEFORE_LOSS", "high",
        "CU reasoning flagged estimate dated before date of loss", 25,
        {"EstimateBeforeLoss"},
    ),
    "narrative_image_consistency": (
        "CU_NARRATIVE_IMAGE_INCONSISTENT", "medium",
        "CU reasoning flagged damage photo inconsistent with claim narrative",
        18, {"Inconsistent"},
    ),
}

_EVIDENCE_SUFFIX = {
    "vin_consistency": "vin_consistency_evidence",
    "totals_vs_sub_limit": "totals_evidence",
    "estimate_date_vs_date_of_loss": "date_evidence",
    "narrative_image_consistency": "narrative_image_evidence",
}


def extract_cu_signals(fraud_fields: ProFraudFields) -> list[FraudSignal]:
    """Map the pro_fraud analyzer's classify findings into FraudSignals."""
    out: list[FraudSignal] = []
    for attr, (rule_id, sev, title, weight, bad) in _CU_SIGNAL_MAP.items():
        v = getattr(fraud_fields, attr, None)
        if not v or v not in bad:
            continue
        evidence_attr = _EVIDENCE_SUFFIX.get(attr)
        evidence = (getattr(fraud_fields, evidence_attr, None) if evidence_attr else None) \
            or f"Pro-mode analyzer classified `{attr}` as `{v}`."
        out.append(FraudSignal(
            rule_id=rule_id,
            severity=sev,
            title=title,
            evidence=str(evidence)[:1000],
            source_documents=["pro_fraud analyzer reasoning"],
            weight=weight,
        ))
    return out


# ── High-level entrypoints ─────────────────────────────────────────────────
def analyze_claims(files: list[Path], *, sample_id: Optional[str] = None) -> ProClaimsResult:
    t0 = time.perf_counter()
    raw = analyze_multi(ANALYZER_CLAIMS_ID, files)
    elapsed = time.perf_counter() - t0
    fields = project_claims_fields(raw)
    return ProClaimsResult(
        meta=ProMeta(
            sample_id=sample_id,
            scenario="claims",
            analyzer_id=ANALYZER_CLAIMS_ID,
            api_version=API_VERSION,
            elapsed_sec=round(elapsed, 2),
            input_files=[p.name for p in files],
        ),
        fields=fields,
        raw=raw,
    )


def analyze_fraud(files: list[Path], *, sample_id: Optional[str] = None) -> ProFraudResult:
    t0 = time.perf_counter()

    # Run BOTH analyzers concurrently? For simplicity, run sequentially —
    # the fraud analyzer drives the CU signals, the claims analyzer drives
    # the rule engine inputs.
    raw_claims = analyze_multi(ANALYZER_CLAIMS_ID, files)
    raw_fraud = analyze_multi(ANALYZER_FRAUD_ID, files)
    elapsed = time.perf_counter() - t0

    claims_fields = project_claims_fields(raw_claims)
    fraud_fields = project_fraud_fields(raw_fraud)

    cu_signals = extract_cu_signals(fraud_fields)

    # Rule engine — for the dates we prefer the estimate date if the
    # pro_fraud DateEvidence narrative contains one.
    estimate_date = _scrape_estimate_date(fraud_fields.date_evidence)
    rule_signals = fraud_rules.evaluate(
        claimant_name=claims_fields.claimant_name,
        policy_number=claims_fields.policy_number,
        vin=claims_fields.vin,
        date_of_loss=claims_fields.date_of_loss,
        estimated_total=claims_fields.estimated_total,
        estimate_date=estimate_date,
    )
    score, band = fraud_rules.blend_risk_score(cu_signals, rule_signals)

    return ProFraudResult(
        meta=ProMeta(
            sample_id=sample_id,
            scenario="fraud",
            analyzer_id=ANALYZER_FRAUD_ID,
            api_version=API_VERSION,
            elapsed_sec=round(elapsed, 2),
            input_files=[p.name for p in files],
        ),
        fields=fraud_fields,
        cu_signals=cu_signals,
        rule_signals=rule_signals,
        risk_score=score,
        risk_band=band,
        raw={"claims": raw_claims, "fraud": raw_fraud},
    )


def _scrape_estimate_date(date_evidence: Optional[str]) -> Optional[str]:
    """Pull an ISO YYYY-MM-DD out of the analyzer's date_evidence text."""
    if not date_evidence:
        return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})", date_evidence)
    return m.group(1) if m else None


def healthcheck() -> dict[str, Any]:
    info: dict[str, Any] = {
        "api_version": API_VERSION,
        "endpoint_configured": False,
        "analyzers": {},
        "samples_available": [m.id for m in list_sample_manifests()],
        "pro_mode_supported": None,
        "error": None,
    }
    try:
        _endpoint()
        info["endpoint_configured"] = True
    except RuntimeError as exc:
        info["error"] = str(exc)
        return info
    try:
        with httpx.Client(timeout=20.0) as client:
            for aid in (ANALYZER_CLAIMS_ID, ANALYZER_FRAUD_ID):
                info["analyzers"][aid] = analyzer_exists(aid, client=client)
        info["pro_mode_supported"] = True
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"
        info["pro_mode_supported"] = False
    return info
