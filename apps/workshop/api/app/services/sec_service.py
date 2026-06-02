"""SEC financial-table extraction service.

Source of truth for the SEC demo logic that previously lived in
SECExtraction/notebooks/2_extraction_comparison.ipynb. The router
(app/routers/sec.py) and the demo/sec notebooks are thin callers of this
module so there is exactly one implementation.

Two-stage Content Understanding workflow:
  1. Classifier (`secClassifierV1`) — segments a SEC filing into the
     five primary consolidated financial statement categories
     (BalanceSheet, IncomeStatement, ComprehensiveIncome, Equity,
     CashFlow) plus Other. `contentCategories[<cat>].analyzerId` routes
     each non-Other segment to the analyzer in the same call.
  2. Analyzer (`secFinancialTablesV1`) — extracts row hierarchy
     (level, isSectionHeader, isSubtotal) for each financial table.

The classifier's `begin_analyze_binary` returns a single response with
per-segment `contents[]`. We retry the call (up to MAX_RETRIES extra
times) when any non-Other segment came back with zero rows, since CU
extraction is non-deterministic for sparse tables.
"""
from __future__ import annotations

import json
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

from azure.ai.contentunderstanding import ContentUnderstandingClient

from helpers.azure_credential_utils import get_azure_credential
from app.services import cost
from app.services import sec_excel

# ── Paths / config ──────────────────────────────────────────────────────────
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[5]  # api/app/services/sec_service.py -> repo root


def _resolve_demo_root() -> Path:
    env = os.environ.get("SEC_DEMO_ROOT")
    if env:
        return Path(env).resolve()
    return REPO_ROOT / "demo" / "sec"


SEC_DEMO_ROOT = _resolve_demo_root()
ATTACH_DIR = SEC_DEMO_ROOT / "attachments"
TEMPLATE_DIR = SEC_DEMO_ROOT / "reference" / "analyzer-templates"
CU_OUTPUT_DIR = SEC_DEMO_ROOT / "reference" / "cu-output"
EXPECTED_DIR = SEC_DEMO_ROOT / "reference" / "expected-output"

CLASSIFIER_ID = "secClassifierV1"
ANALYZER_ID = "secFinancialTablesV1"
CLASSIFIER_TEMPLATE = "sec_classifier.json"
ANALYZER_TEMPLATE = "sec_financial_tables.json"

EXPECTED_CATEGORIES = [
    "BalanceSheet",
    "IncomeStatement",
    "ComprehensiveIncome",
    "Equity",
    "CashFlow",
]

MAX_RETRIES = 2  # retry up to this many extra times if any segment has 0 rows


# ── Client / template loading ──────────────────────────────────────────────
@lru_cache(maxsize=1)
def _client() -> ContentUnderstandingClient:
    endpoint = (
        os.environ.get("APP_CONTENT_UNDERSTANDING_ENDPOINT")
        or os.environ.get("CONTENTUNDERSTANDING_ENDPOINT")
        or os.environ.get("FOUNDRY_ENDPOINT")
    )
    if not endpoint:
        raise RuntimeError(
            "Set APP_CONTENT_UNDERSTANDING_ENDPOINT in the repo root .env "
            "(or apps/workshop/api/.env) before calling the SEC service."
        )
    return ContentUnderstandingClient(endpoint=endpoint, credential=get_azure_credential())


def _load_template(name: str) -> dict[str, Any]:
    return json.loads((TEMPLATE_DIR / name).read_text(encoding="utf-8"))


def _classifier_template() -> dict[str, Any]:
    """Load classifier template and substitute the analyzer ID + optional models."""
    tmpl = _load_template(CLASSIFIER_TEMPLATE)
    cats = tmpl.get("config", {}).get("contentCategories", {})
    for cat in cats.values():
        if cat.get("analyzerId") == "__ANALYZER_ID__":
            cat["analyzerId"] = ANALYZER_ID
    _inject_models(tmpl)
    return tmpl


def _analyzer_template() -> dict[str, Any]:
    tmpl = _load_template(ANALYZER_TEMPLATE)
    # The analyzer fieldSchema has `method: classify` / `method: extract`
    # entries that require an LLM. The resource has no default model, so
    # we must wire one explicitly — same pattern the SOV analyzers use.
    _inject_models(tmpl)
    return tmpl


def _inject_models(tmpl: dict[str, Any]) -> None:
    """Add a top-level `models` block to a CU analyzer/classifier template
    using env-configured deployment names. No-op when nothing is set."""
    completion = (
        os.environ.get("APP_CU_COMPLETION_DEPLOYMENT")
        or os.environ.get("GPT41_MINI_MODEL_DEPLOYMENT")
        or os.environ.get("GPT41_MODEL_DEPLOYMENT")
    )
    embedding = os.environ.get("EMBEDDING_MODEL_DEPLOYMENT") or os.environ.get(
        "APP_CU_EMBEDDING_DEPLOYMENT"
    )
    if completion or embedding:
        models = tmpl.setdefault("models", {})
        if completion:
            models["completion"] = completion
        if embedding:
            models["embedding"] = embedding


# ── Analyzer deployment ────────────────────────────────────────────────────
def ensure_analyzers(force_replace: bool = False) -> dict[str, str]:
    """Idempotently deploy the analyzer + classifier to Content Understanding.

    Returns a mapping of role → analyzer ID. Safe to call on every request;
    skips deployment when the analyzers already exist (unless `force_replace`).
    """
    client = _client()
    statuses: dict[str, str] = {}

    def _deploy(analyzer_id: str, template: dict[str, Any]) -> str:
        if not force_replace:
            try:
                client.get_analyzer(analyzer_id=analyzer_id)
                return "exists"
            except Exception:
                pass
        poller = client.begin_create_analyzer(
            analyzer_id=analyzer_id,
            resource=template,
            allow_replace=True,
        )
        poller.result()
        return "created"

    # Analyzer must exist before classifier references it.
    statuses[ANALYZER_ID] = _deploy(ANALYZER_ID, _analyzer_template())
    statuses[CLASSIFIER_ID] = _deploy(CLASSIFIER_ID, _classifier_template())
    return statuses


# ── Classification + extraction (single call, retries on empties) ──────────
def _has_empty_tables(result: dict[str, Any]) -> list[str]:
    """Return categories whose financialTables have at least one 0-row table."""
    empties: list[str] = []
    for seg in result.get("contents", []):
        cat = seg.get("category", "Other")
        if cat == "Other":
            continue
        ft = (seg.get("fields") or {}).get("financialTables", {}) or {}
        for tbl in ft.get("valueArray", []) or []:
            tobj = tbl.get("valueObject", {}) or {}
            rows = (tobj.get("rows") or {}).get("valueArray") or []
            if len(rows) == 0:
                empties.append(cat)
                break
    return empties


def classify_and_extract(pdf_bytes: bytes, *, max_retries: int = MAX_RETRIES) -> tuple[dict[str, Any], int]:
    """Run the classifier on a PDF, retrying on empty extracted tables.

    Returns (raw_result, retries_consumed). The classifier delegates each
    segment to the analyzer via `contentCategories[*].analyzerId`, so this
    one call exercises both stages.
    """
    client = _client()
    attempt = 0
    while True:
        poller = client.begin_analyze_binary(
            analyzer_id=CLASSIFIER_ID,
            binary_input=pdf_bytes,
            content_type="application/pdf",
        )
        result = poller.result().as_dict()
        empties = _has_empty_tables(result)
        if not empties or attempt >= max_retries:
            return result, attempt
        attempt += 1


# ── Segment merging ────────────────────────────────────────────────────────
def merge_segments(raw_result: dict[str, Any]) -> dict[str, Any]:
    """Flatten per-category segments into one merged CU payload.

    The classifier returns multiple `contents[]` entries (one per segment).
    For Excel export and downstream rendering we want a single
    `contents[0].fields.financialTables` array that concatenates every
    non-Other segment's tables, preserving classifier-assigned order.

    Source provenance (category, page range) is preserved by annotating
    each table with `_segmentCategory`, `_pageStart`, `_pageEnd`.
    """
    merged_tables: list[dict[str, Any]] = []
    for seg in raw_result.get("contents", []) or []:
        cat = seg.get("category", "Other")
        if cat == "Other":
            continue
        ft = (seg.get("fields") or {}).get("financialTables", {}) or {}
        for tbl in ft.get("valueArray", []) or []:
            annotated = dict(tbl)
            annotated["_segmentCategory"] = cat
            annotated["_pageStart"] = seg.get("startPageNumber")
            annotated["_pageEnd"] = seg.get("endPageNumber")
            merged_tables.append(annotated)

    merged: dict[str, Any] = {
        "contents": [
            {
                "fields": {
                    "financialTables": {
                        "type": "array",
                        "valueArray": merged_tables,
                    }
                }
            }
        ]
    }
    # Preserve CU's `usage` block when present so cost.estimate_cu_cost works.
    if "usage" in raw_result:
        merged["usage"] = raw_result["usage"]
    return merged


def segment_category_counts(raw_result: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for seg in raw_result.get("contents", []) or []:
        cat = seg.get("category", "Unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def missing_categories(raw_result: dict[str, Any]) -> list[str]:
    found = {
        seg.get("category")
        for seg in raw_result.get("contents", []) or []
        if seg.get("category") != "Other"
    }
    return [c for c in EXPECTED_CATEGORIES if c not in found]


# ── Excel export wrapper ───────────────────────────────────────────────────
def export_to_excel(merged_payload: dict[str, Any], out_path: Path) -> Path:
    """Render a merged CU payload to a multi-sheet .xlsx workbook."""
    return sec_excel.export_payload(merged_payload, out_path)


# ── Projection: CU payload -> SecExtractionResult ──────────────────────────
def project_result(
    merged_payload: dict[str, Any],
    *,
    file_name: str,
    meta_extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Project a merged CU payload to the SecExtractionResult shape.

    Returns a plain dict; the router will coerce via the Pydantic model.
    Uses sec_excel's normalizer so the UI sees the same hierarchy fixups
    the Excel export applies.
    """
    normalized = sec_excel.load_from_payload(merged_payload)
    raw_tables = (
        ((merged_payload.get("contents") or [{}])[0].get("fields") or {})
        .get("financialTables", {})
        .get("valueArray", [])
        or []
    )

    statements = []
    for norm, raw in zip(normalized, raw_tables):
        statements.append({
            "statement_type": norm["statementType"] or "Other",
            "table_title": norm["tableTitle"],
            "company_name": norm["companyName"],
            "unit": norm["unit"],
            "period_headers": norm["periodHeaders"],
            "period_groups": norm["periodGroups"],
            "rows": [
                {
                    "line_item": r["lineItem"],
                    "level": r["level"],
                    "is_section_header": r["isSectionHeader"],
                    "is_subtotal": r["isSubtotal"],
                    "values": r["values"],
                    "value_confidences": r.get("valueConfidences"),
                    "confidence": r.get("confidence"),
                }
                for r in norm["rows"]
            ],
            "source_category": raw.get("_segmentCategory"),
            "page_start": raw.get("_pageStart"),
            "page_end": raw.get("_pageEnd"),
        })

    # NOTE: `page_start` / `page_end` are populated only when the merged
    # payload carries CU segment metadata (`_pageStart`, `_pageEnd`). Legacy
    # cached fixtures that were pre-flattened on disk lose that information;
    # for those samples the UI will leave the click-to-jump action inert
    # rather than guess. Run with `use_cache=False` once to refresh.

    meta = {
        "source_file": file_name,
        "classifier_id": CLASSIFIER_ID,
        "analyzer_id": ANALYZER_ID,
    }
    if meta_extra:
        meta.update(meta_extra)

    return {
        "file_name": file_name,
        "meta": meta,
        "statements": statements,
        "raw": merged_payload,
    }


# ── Samples & cache ──────────────────────────────────────────────────────────────
def list_samples() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not ATTACH_DIR.exists():
        return out
    for p in sorted(ATTACH_DIR.iterdir()):
        if p.suffix.lower() != ".pdf":
            continue
        cached = (CU_OUTPUT_DIR / f"{p.stem}_v2_classified.json").exists() or (
            CU_OUTPUT_DIR / f"{p.stem}.json"
        ).exists()
        gt = (EXPECTED_DIR / f"{p.stem}.json").exists()
        out.append({
            "file_name": p.name,
            "file_type": "pdf",
            "size_kb": round(p.stat().st_size / 1024, 1),
            "has_cached_result": cached,
            "has_ground_truth": gt,
        })
    return out


def _cache_path(sample_name: str) -> Path:
    stem = Path(sample_name).stem
    # Prefer the SECExtraction-style filename when present (ships with the
    # repo); fall back to the simpler `<stem>.json` for newly captured runs.
    legacy = CU_OUTPUT_DIR / f"{stem}_v2_classified.json"
    if legacy.exists():
        return legacy
    return CU_OUTPUT_DIR / f"{stem}.json"


def load_cached_payload(sample_name: str) -> Optional[dict[str, Any]]:
    p = _cache_path(sample_name)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_cached_payload(sample_name: str, payload: dict[str, Any]) -> Path:
    CU_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    p = CU_OUTPUT_DIR / f"{Path(sample_name).stem}.json"
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


# ── Full extraction orchestrator ───────────────────────────────────────────
def run_extraction(
    sample_name: str,
    *,
    use_cache: bool = True,
    save_as_canonical: bool = False,
    excel_out: Optional[Path] = None,
) -> dict[str, Any]:
    """End-to-end orchestration mirroring the SEC page's "Run" button.

    Steps:
      1. (cache) Try cached merged payload from `demo/sec/reference/cu-output/`.
      2. Otherwise: ensure analyzers deployed, classify+extract with retries,
         merge segments.
      3. Write `.xlsx` artifact when `excel_out` is given.
      4. Project to SecExtractionResult shape.

    Returns the dict ready to be coerced into SecExtractionResult.
    """
    src = ATTACH_DIR / sample_name
    if not src.exists():
        raise FileNotFoundError(f"Sample not found: {sample_name}")

    t0 = time.time()
    from_cache = False
    retries = 0
    raw_result: Optional[dict[str, Any]] = None

    if use_cache:
        cached = load_cached_payload(sample_name)
        if cached is not None:
            contents = cached.get("contents") or []
            # Detect cache shape: raw CU responses carry `category` (and
            # `startPageNumber`/`endPageNumber`) on each segment; legacy
            # pre-flattened caches have a single content with no category.
            has_segments = any("category" in c for c in contents)
            if has_segments:
                # Re-merge from raw on every load so page metadata flows through.
                merged = merge_segments(cached)
            else:
                # Legacy already-merged fixture — page metadata is unavailable.
                merged = cached
            from_cache = True

    if not from_cache:
        raw_result, retries = classify_and_extract(src.read_bytes())
        merged = merge_segments(raw_result)
        if save_as_canonical:
            # Cache the RAW response so future loads can recover per-segment
            # page metadata via merge_segments. (Cost note: cached payloads
            # do not carry a `usage` block, so the cost pill will read n/a.)
            save_cached_payload(sample_name, raw_result)

    elapsed = time.time() - t0

    artifacts: dict[str, str] = {}
    if excel_out is not None:
        export_to_excel(merged, excel_out)
        artifacts["excel"] = str(excel_out)

    seg_counts = segment_category_counts(raw_result) if raw_result else {}
    missing = missing_categories(raw_result) if raw_result else []

    meta_extra = {
        "elapsed_sec": round(elapsed, 2),
        "retries": retries,
        "segment_categories": seg_counts,
        "missing_statements": missing,
        "from_cache": from_cache,
        "artifacts": artifacts,
        "cost": cost.estimate_cu_cost(merged) if merged.get("usage") else {},
    }
    return project_result(merged, file_name=sample_name, meta_extra=meta_extra)


# ── Validation against expected output ─────────────────────────────────────
def validate(result: dict[str, Any]) -> dict[str, Any]:
    """Compare a SecExtractionResult against demo/sec/reference/expected-output."""
    file_name = result.get("file_name") or result.get("meta", {}).get("source_file") or ""
    stem = Path(file_name).stem
    expected_path = EXPECTED_DIR / f"{stem}.json"
    if not expected_path.exists():
        return {
            "file_name": file_name,
            "has_ground_truth": False,
            "statements": [],
            "overall_match_rate": 0.0,
        }
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    expected_by_type: dict[str, list[str]] = {}
    for st in expected.get("statements", []) or []:
        expected_by_type[st["statement_type"]] = [
            (r.get("line_item") or "").strip().lower() for r in st.get("rows", [])
        ]

    summaries: list[dict[str, Any]] = []
    total_expected = 0
    total_matched = 0
    for st in result.get("statements", []) or []:
        stype = st.get("statement_type") or "Other"
        exp_rows = expected_by_type.get(stype, [])
        actual_rows = [
            (r.get("line_item") or "").strip().lower() for r in st.get("rows", [])
        ]
        exp_set = set(exp_rows)
        act_set = set(actual_rows)
        matched = exp_set & act_set
        missing = sorted(exp_set - act_set)
        extra = sorted(act_set - exp_set)
        summaries.append({
            "statement_type": stype,
            "expected_rows": len(exp_rows),
            "actual_rows": len(actual_rows),
            "matched_rows": len(matched),
            "missing_rows": missing,
            "extra_rows": extra,
        })
        total_expected += len(exp_rows)
        total_matched += len(matched)

    overall = (total_matched / total_expected) if total_expected else 0.0
    return {
        "file_name": file_name,
        "has_ground_truth": True,
        "statements": summaries,
        "overall_match_rate": round(overall, 4),
    }


# ── Ground-truth authoring ─────────────────────────────────────────────────
def save_as_expected(result: dict[str, Any]) -> Path:
    """Persist the line-item shell of a SecExtractionResult as ground truth.

    Writes to ``demo/sec/reference/expected-output/<stem>.json``. Only the
    fields the validator cares about (`statement_type` + per-row
    `line_item`) are kept, so reviewers can curate without seeing model
    confidence noise. Idempotent — overwrites any existing file.
    """
    file_name = result.get("file_name") or result.get("meta", {}).get("source_file") or ""
    if not file_name:
        raise ValueError("Result is missing file_name")
    stem = Path(file_name).stem
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPECTED_DIR / f"{stem}.json"

    payload = {
        "file_name": file_name,
        "statements": [
            {
                "statement_type": st.get("statement_type"),
                "table_title": st.get("table_title", ""),
                "rows": [
                    {"line_item": (r.get("line_item") or "").strip()}
                    for r in st.get("rows", []) or []
                    if (r.get("line_item") or "").strip()
                ],
            }
            for st in result.get("statements", []) or []
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path
