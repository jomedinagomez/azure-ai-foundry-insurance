"""SOV extraction & validation service.

Source of truth for the SOV demo logic that previously lived in
demo/sov/notebooks/01_extract_sov.ipynb and 02_validate_extraction.ipynb.
The router (app/routers/sov.py) is a thin wrapper around this module.

Patterns:
- A (standard-extract):   PDF                              -> sovExtractV1
- B (standard-generate):  xlsx, no embedded images         -> sovGenerateV1
- C (pattern-c):          xlsx WITH embedded images        -> sovGenerateV1
                          (workbook + per-image fan-out, merged client-side)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.identity import DefaultAzureCredential

# ── Paths / config ──────────────────────────────────────────────────────────
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[5]  # api/app/services/sov_service.py -> repo root


def _resolve_demo_root() -> Path:
    env = os.environ.get("SOV_DEMO_ROOT")
    if env:
        return Path(env).resolve()
    return REPO_ROOT / "demo" / "sov"


SOV_DEMO_ROOT = _resolve_demo_root()
ATTACH_DIR = SOV_DEMO_ROOT / "attachments"
TEMPLATE_DIR = SOV_DEMO_ROOT / "reference" / "analyzer-templates"
CU_OUTPUT_DIR = SOV_DEMO_ROOT / "reference" / "cu-output"
EXPECTED_DIR = SOV_DEMO_ROOT / "reference" / "expected-output"

ANALYZER_EXTRACT_ID = "sovExtractV1"
ANALYZER_GENERATE_ID = "sovGenerateV1"

CONTENT_TYPE_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
}

ACCOUNT_FIELD_MAP = {
    "InsuredName": "insured_name", "DBA": "dba", "MailingAddress": "mailing_address",
    "EffectiveDate": "effective_date", "ExpirationDate": "expiration_date",
    "PrimaryOperations": "primary_operations", "NAICS": "naics", "Currency": "currency",
    "ValuationDate": "valuation_date", "TotalInsuredValue": "total_insured_value",
    "LocationCount": "location_count", "BrokerName": "broker_name",
    "BrokerContact": "broker_contact", "BrokerEmail": "broker_email",
    "BrokerPhone": "broker_phone", "PreparedBy": "prepared_by", "PreparedDate": "prepared_date",
}
LOCATION_FIELD_MAP = {
    "LocationNumber": "location_number", "BuildingNumber": "building_number",
    "Street": "street", "City": "city", "State": "state", "Zip": "zip",
    "ConstructionType": "construction_type", "Occupancy": "occupancy",
    "OperationsDescription": "operations_description", "YearBuilt": "year_built",
    "Stories": "stories", "SquareFootage": "square_footage", "UnitCount": "unit_count",
    "BuildingValue": "building_value", "BPPValue": "bpp_value", "BIEEValue": "bi_ee_value",
    "Sprinklered": "sprinklered", "ProtectionClass": "protection_class",
    "RoofYear": "roof_year", "FloodZone": "flood_zone",
    "DistanceToCoastMiles": "distance_to_coast_mi", "Notes": "notes",
}

APPROACH_TO_PATTERN = {
    "standard-extract": "A",
    "standard-generate": "B",
    "pattern-c-xlsx-plus-image-merge": "C",
}


# ── Client / templates (cached) ────────────────────────────────────────────
@lru_cache(maxsize=1)
def _client() -> ContentUnderstandingClient:
    endpoint = (
        os.environ.get("APP_CONTENT_UNDERSTANDING_ENDPOINT")
        or os.environ.get("CONTENTUNDERSTANDING_ENDPOINT")
        or os.environ.get("FOUNDRY_ENDPOINT")
    )
    if not endpoint:
        raise RuntimeError(
            "Set APP_CONTENT_UNDERSTANDING_ENDPOINT in apps/workshop/api/.env"
        )
    return ContentUnderstandingClient(endpoint=endpoint, credential=DefaultAzureCredential())


@lru_cache(maxsize=4)
def _template(name: str) -> dict:
    return json.loads((TEMPLATE_DIR / name).read_text(encoding="utf-8"))


def _ensure_analyzer(analyzer_id: str, template_name: str) -> str:
    client = _client()
    try:
        client.get_analyzer(analyzer_id=analyzer_id)
        return analyzer_id
    except Exception:
        pass
    poller = client.begin_create_analyzer(
        analyzer_id=analyzer_id, resource=_template(template_name)
    )
    poller.result()
    return analyzer_id


# ── Pattern-C plumbing (xlsx image extraction + merge) ─────────────────────
def _extract_embedded_images(xlsx_path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    try:
        with zipfile.ZipFile(xlsx_path) as zf:
            media = sorted(n for n in zf.namelist() if n.startswith("xl/media/"))
            for i, name in enumerate(media, start=1):
                ext = Path(name).suffix.lower() or ".png"
                target = out_dir / f"{xlsx_path.stem}_image{i:02d}{ext}"
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                paths.append(target)
    except zipfile.BadZipFile:
        pass
    return paths


def _location_key(loc_obj: dict) -> tuple:
    obj = loc_obj.get("valueObject", {}) if isinstance(loc_obj, dict) else {}

    def val(field: str):
        f = obj.get(field) or {}
        for k in ("valueNumber", "valueInteger", "valueString"):
            if k in f and f[k] is not None:
                return f[k]
        return None

    return (val("LocationNumber"), (val("Street") or "").strip().lower())


def _field_has_value(field: dict) -> bool:
    if not isinstance(field, dict):
        return False
    for k in ("valueString", "valueNumber", "valueInteger", "valueDate",
              "valueBoolean", "valueArray", "valueObject"):
        if k in field and field[k] not in (None, "", [], {}):
            return True
    return False


def _merge_image_locations(
    primary: list[dict], batches: list[list[dict]]
) -> tuple[list[dict], int, int]:
    out = list(primary)
    by_key = {_location_key(r): r for r in out}
    added = 0
    complements = 0
    for batch_idx, batch in enumerate(batches):
        for img_loc in batch:
            k = _location_key(img_loc)
            existing = by_key.get(k)
            img_obj = img_loc.get("valueObject", {}) if isinstance(img_loc, dict) else {}
            if existing is None:
                img_loc.setdefault("_source", f"image[{batch_idx}]")
                out.append(img_loc)
                by_key[k] = img_loc
                added += 1
                continue
            ex_obj = existing.setdefault("valueObject", {})
            row_complemented = False
            for fname, ifield in img_obj.items():
                if not _field_has_value(ifield):
                    continue
                efield = ex_obj.get(fname)
                if efield is None or not _field_has_value(efield):
                    ex_obj[fname] = ifield
                    complements += 1
                    row_complemented = True
            if row_complemented:
                src = existing.get("_source", "xlsx")
                if isinstance(src, str) and "image" not in src:
                    existing["_source"] = f"{src}+image[{batch_idx}]"
    return out, added, complements


def _result_to_dict(result) -> dict:
    if hasattr(result, "as_dict"):
        return result.as_dict()
    return json.loads(json.dumps(result, default=lambda o: getattr(o, "__dict__", str(o))))


def _analyze_one(path: Path, analyzer_id: str, template_name: str, content_type: str) -> tuple[dict, float]:
    _ensure_analyzer(analyzer_id, template_name)
    t0 = time.perf_counter()
    with open(path, "rb") as f:
        poller = _client().begin_analyze_binary(
            analyzer_id=analyzer_id,
            binary_input=f.read(),
            content_type=content_type,
        )
    return _result_to_dict(poller.result()), time.perf_counter() - t0


# ── Public: extraction ──────────────────────────────────────────────────────
def list_samples() -> list[dict]:
    """Discover the SOV sample files; return shape used by SovSample schema."""
    out: list[dict] = []
    if not ATTACH_DIR.exists():
        return out
    for p in sorted(ATTACH_DIR.iterdir()):
        if p.suffix.lower() not in {".xlsx", ".pdf"}:
            continue
        if p.name.startswith("~$"):  # Excel lock files
            continue
        out.append({
            "file_name": p.name,
            "file_type": p.suffix.lower().lstrip("."),
            "size_kb": round(p.stat().st_size / 1024, 1),
            "has_cached_result": (CU_OUTPUT_DIR / f"{p.stem}.json").exists(),
            "has_ground_truth": (EXPECTED_DIR / f"{_expected_stem(p.stem)}.json").exists(),
        })
    return out


def _expected_stem(cu_stem: str) -> str:
    return cu_stem[:-4] if cu_stem.lower().endswith("_sov") else cu_stem


def get_cached_payload(sample_name: str) -> Optional[dict]:
    stem = Path(sample_name).stem
    p = CU_OUTPUT_DIR / f"{stem}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def save_cached_payload(sample_name: str, payload: dict) -> None:
    """Persist an arbitrary CU payload to the on-disk cache for this sample."""
    stem = Path(sample_name).stem
    if not (ATTACH_DIR / sample_name).exists():
        raise FileNotFoundError(f"Sample not found: {sample_name}")
    CU_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = CU_OUTPUT_DIR / f"{stem}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_expected(sample_name: str) -> Optional[dict]:
    stem = _expected_stem(Path(sample_name).stem)
    p = EXPECTED_DIR / f"{stem}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


# ── Analyzer template management ────────────────────────────────────────────
ANALYZER_TEMPLATES = [
    {"id": ANALYZER_EXTRACT_ID, "template_file": "sov_extraction.json",
     "method": "extract", "use_case": "PDF (Patterns A)"},
    {"id": ANALYZER_GENERATE_ID, "template_file": "sov_extraction_generate.json",
     "method": "generate", "use_case": "Excel + image fan-out (Patterns B & C)"},
]


def list_analyzers() -> list[dict]:
    out = []
    for entry in ANALYZER_TEMPLATES:
        p = TEMPLATE_DIR / entry["template_file"]
        out.append({
            **entry,
            "exists": p.exists(),
            "size_bytes": p.stat().st_size if p.exists() else 0,
        })
    return out


def _resolve_analyzer_file(template_file: str) -> Path:
    p = TEMPLATE_DIR / template_file
    if not p.exists() or p.parent.resolve() != TEMPLATE_DIR.resolve():
        raise FileNotFoundError(f"Analyzer template not found: {template_file}")
    return p


def get_analyzer_template(template_file: str) -> dict:
    return json.loads(_resolve_analyzer_file(template_file).read_text(encoding="utf-8"))


def save_analyzer_template(template_file: str, content: dict) -> None:
    p = _resolve_analyzer_file(template_file)
    # Validate it's still a JSON object with a baseAnalyzerId etc
    if not isinstance(content, dict) or "baseAnalyzerId" not in content:
        raise ValueError("Template must be a JSON object containing 'baseAnalyzerId'.")
    p.write_text(json.dumps(content, indent=2), encoding="utf-8")
    # Bust the cached template
    _template.cache_clear()


def push_analyzer_to_foundry(analyzer_id: str, template_file: str) -> dict:
    """Delete (if exists) and recreate the analyzer in Foundry from the saved
    template file. Returns timing + status info."""
    template = get_analyzer_template(template_file)
    client = _client()
    deleted = False
    try:
        client.delete_analyzer(analyzer_id=analyzer_id)
        deleted = True
    except Exception:
        pass
    t0 = time.perf_counter()
    poller = client.begin_create_analyzer(analyzer_id=analyzer_id, resource=template)
    poller.result()
    return {
        "analyzer_id": analyzer_id,
        "template_file": template_file,
        "previous_deleted": deleted,
        "elapsed_sec": round(time.perf_counter() - t0, 2),
    }


def analyze_sample(sample_name: str, force_refresh: bool = False, pattern: Optional[str] = None) -> dict:
    """Run extraction for a sample. pattern: 'A'|'B'|'C'|None (auto).
    Setting pattern bypasses cache and overwrites it."""
    src = ATTACH_DIR / sample_name
    if not src.exists():
        raise FileNotFoundError(f"Sample not found: {sample_name}")
    cache_path = CU_OUTPUT_DIR / f"{src.stem}.json"
    if cache_path.exists() and not force_refresh and pattern is None:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        payload.setdefault("_meta", {})["from_cache"] = True
        return payload

    payload = _analyze_path(src, pattern=pattern)
    CU_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Only persist to the shared cache when running in Auto mode. Explicit-pattern
    # runs are throwaway probes and must not overwrite the canonical cache.
    if pattern is None:
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["_meta"]["from_cache"] = False
    return payload


def analyze_uploaded(file_bytes: bytes, file_name: str, pattern: Optional[str] = None) -> dict:
    suffix = Path(file_name).suffix.lower()
    if suffix not in {".pdf", ".xlsx"}:
        raise ValueError(f"Unsupported file type: {suffix}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / file_name
        tmp_path.write_bytes(file_bytes)
        return _analyze_path(tmp_path, pattern=pattern)


def _analyze_path(path: Path, pattern: Optional[str] = None) -> dict:
    """pattern in {'A','B','C',None}.
      A = PDF + extract analyzer.
      B = single-call generate (xlsx workbook only).
      C = generate on workbook + fan-out to embedded images, merged client-side.
    None = auto: A for pdf, C if xlsx has images else B.
    Analyzer + template per pattern come from sov_patterns.json (editable)."""
    suffix = path.suffix.lower()
    if pattern not in (None, "A", "B", "C"):
        raise ValueError(f"Unknown pattern: {pattern}")

    auto = pattern is None
    do_fan_out = pattern == "C" or (auto and suffix == ".xlsx")
    cfg = get_pattern_config()

    # Pattern C: workbook + image fan-out (xlsx only)
    if do_fan_out and suffix == ".xlsx":
        with tempfile.TemporaryDirectory() as tmp:
            image_paths = _extract_embedded_images(path, Path(tmp))
            if image_paths:
                c_aid = cfg["C"]["analyzer_id"]
                c_tpl = cfg["C"]["template_file"]
                payload, t_main = _analyze_one(
                    path, c_aid, c_tpl, CONTENT_TYPE_BY_SUFFIX[".xlsx"]
                )
                batches: list[list[dict]] = []
                t_imgs = 0.0
                for img in image_paths:
                    ip, ie = _analyze_one(
                        img, c_aid, c_tpl, CONTENT_TYPE_BY_SUFFIX[img.suffix.lower()]
                    )
                    t_imgs += ie
                    batches.append(
                        ip.get("contents", [{}])[0]
                          .get("fields", {})
                          .get("Locations", {})
                          .get("valueArray", [])
                    )
                primary = (
                    payload.get("contents", [{}])[0]
                           .get("fields", {})
                           .get("Locations", {})
                           .get("valueArray", [])
                )
                merged, added, complements = _merge_image_locations(primary, batches)
                try:
                    payload["contents"][0]["fields"]["Locations"]["valueArray"] = merged
                    lc = payload["contents"][0]["fields"].setdefault("LocationCount", {"type": "number"})
                    lc["type"] = "number"
                    lc["valueNumber"] = len(merged)
                except (KeyError, IndexError):
                    pass
                payload["_meta"] = {
                    "source_file": path.name,
                    "approach": "pattern-c-xlsx-plus-image-merge",
                    "analyzer_id": c_aid,
                    "image_calls": len(image_paths),
                    "added_from_images": added,
                    "field_complements": complements,
                    "elapsed_main_sec": round(t_main, 2),
                    "elapsed_images_sec": round(t_imgs, 2),
                    "elapsed_total_sec": round(t_main + t_imgs, 2),
                    "pattern_requested": pattern,
                }
                return payload
            # Explicit C with no images -> degrade to B silently

    # Patterns A & B (single call). When user picks an explicit pattern, honor it.
    if pattern in ("A", "B"):
        chosen = cfg[pattern]
        approach = "standard-extract" if pattern == "A" else "standard-generate"
    elif pattern == "C":
        # Explicit C with no images (no-image xlsx or pdf): single-call generate using C's analyzer.
        chosen = cfg["C"]
        approach = "standard-generate"
    elif suffix == ".pdf":
        chosen = cfg["A"]
        approach = "standard-extract"
    else:
        chosen = cfg["B"]
        approach = "standard-generate"

    payload, elapsed = _analyze_one(
        path, chosen["analyzer_id"], chosen["template_file"], CONTENT_TYPE_BY_SUFFIX[suffix]
    )
    payload["_meta"] = {
        "source_file": path.name,
        "approach": approach,
        "analyzer_id": chosen["analyzer_id"],
        "elapsed_sec": round(elapsed, 2),
        "pattern_requested": pattern,
    }
    return payload


# ── Pattern config (sov_patterns.json) ──────────────────────────────────────
PATTERN_CONFIG_PATH = Path(__file__).parent / "sov_patterns.json"


def get_pattern_config() -> dict:
    if PATTERN_CONFIG_PATH.exists():
        return json.loads(PATTERN_CONFIG_PATH.read_text(encoding="utf-8"))
    return {
        "A": {"analyzer_id": ANALYZER_EXTRACT_ID, "template_file": "sov_extraction.json"},
        "B": {"analyzer_id": ANALYZER_GENERATE_ID, "template_file": "sov_extraction_generate.json"},
        "C": {"analyzer_id": ANALYZER_GENERATE_ID, "template_file": "sov_extraction_generate.json"},
    }


def set_pattern_config(pattern: str, analyzer_id: str, template_file: str) -> dict:
    if pattern not in {"A", "B", "C"}:
        raise ValueError(f"Unknown pattern: {pattern}")
    # Validate template exists
    _resolve_analyzer_file(template_file)
    cfg = get_pattern_config()
    cfg[pattern] = {"analyzer_id": analyzer_id, "template_file": template_file}
    PATTERN_CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


# ── Result projection (CU payload -> SovExtractionResult-shaped dict) ──────
def _unwrap(field: Optional[dict]):
    if not field:
        return None
    for key in ("valueString", "valueNumber", "valueDate",
                "valueInteger", "valueBoolean"):
        if key in field and field[key] is not None:
            return field[key]
    if "valueArray" in field:
        return field["valueArray"]
    if "valueObject" in field:
        return field["valueObject"]
    return None


def _conf(field: Optional[dict]) -> Optional[float]:
    if not isinstance(field, dict):
        return None
    c = field.get("confidence")
    return float(c) if isinstance(c, (int, float)) else None


def cu_account(payload: dict) -> dict:
    contents = (payload.get("result") or payload).get("contents", [])
    fields = contents[0].get("fields", {}) if contents else {}
    return {snake: _unwrap(fields.get(pas)) for pas, snake in ACCOUNT_FIELD_MAP.items()}


def cu_account_confidence(payload: dict) -> dict:
    contents = (payload.get("result") or payload).get("contents", [])
    fields = contents[0].get("fields", {}) if contents else {}
    return {snake: _conf(fields.get(pas)) for pas, snake in ACCOUNT_FIELD_MAP.items()}


def cu_locations(payload: dict) -> list[dict]:
    contents = (payload.get("result") or payload).get("contents", [])
    fields = contents[0].get("fields", {}) if contents else {}
    arr = _unwrap(fields.get("Locations")) or []
    out = []
    for entry in arr:
        obj = entry.get("valueObject", {}) if isinstance(entry, dict) else {}
        row = {snake: _unwrap(obj.get(pas)) for pas, snake in LOCATION_FIELD_MAP.items()}
        if isinstance(entry, dict) and "_source" in entry:
            row["source"] = entry["_source"]
        out.append(row)
    return out


def cu_locations_confidence(payload: dict) -> list[dict]:
    contents = (payload.get("result") or payload).get("contents", [])
    fields = contents[0].get("fields", {}) if contents else {}
    arr = _unwrap(fields.get("Locations")) or []
    out = []
    for entry in arr:
        obj = entry.get("valueObject", {}) if isinstance(entry, dict) else {}
        out.append({snake: _conf(obj.get(pas)) for pas, snake in LOCATION_FIELD_MAP.items()})
    return out


def project_result(payload: dict) -> dict:
    """Shape a CU payload to match SovExtractionResult."""
    meta = payload.get("_meta", {}) or {}
    approach = meta.get("approach", "standard-extract")
    pipeline_id = meta.get("pipeline_id")

    # Map pipeline ids to the historical Pattern letter so the result header
    # badge keeps working without UI changes.
    PIPELINE_TO_PATTERN = {
        "pdf_extract": "A",
        "xlsx_generate": "B",
        "xlsx_generate_with_images": "C",
        "xlsx_via_pdf_tiff": "A",  # same analyzer as PDF extract
    }
    if pipeline_id in PIPELINE_TO_PATTERN:
        pattern = PIPELINE_TO_PATTERN[pipeline_id]
    else:
        pattern = APPROACH_TO_PATTERN.get(approach, "A")

    locations = cu_locations(payload)
    return {
        "file_name": meta.get("source_file", ""),
        "meta": {
            **meta,
            "pattern": pattern,
            "from_cache": bool(meta.get("from_cache", False)),
        },
        "account": cu_account(payload),
        "account_confidence": cu_account_confidence(payload),
        "locations": locations,
        "locations_confidence": cu_locations_confidence(payload),
        "location_count_actual": len(locations),
        "raw": payload,
    }


# ── Validation (port of 02_validate_extraction.ipynb _norm + diff) ─────────
_TRUE = {"yes", "y", "true", "t", "1", "sprinklered"}
_FALSE = {"no", "n", "false", "f", "0", "unsprinklered"}
_PLACEHOLDERS = {"", "-", "--", "—", "–", "n/a", "na", "n.a.", "none", "null", "tbd", "."}
_TRANSLATE = str.maketrans({
    "—": "-", "–": "-", "−": "-", "\u2010": "-", "\u2011": "-",
    "\u201c": '"', "\u201d": '"',
    "\u2018": "'", "\u2019": "'",
    "\u00a0": " ",
})
_WS_RE = re.compile(r"\s+")
_FOOTNOTE_RE = re.compile(r"\s*\(\d+\)\s*")
_MARGIN_PREFIX_RE = re.compile(r"^margin note:\s*", re.I)
_TRUNC_SUFFIX_RE = re.compile(r"[.\s]*\u2026+\s*$")
_TRAIL_PUNCT_RE = re.compile(r"[.,;:\s]+$")


def _norm(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        try:
            import math
            if isinstance(v, float) and math.isnan(v):
                return None
        except Exception:
            pass
        return float(v)
    s = str(v).translate(_TRANSLATE).strip()
    s = _WS_RE.sub(" ", s)
    if not s:
        return None
    low = s.lower()
    low = _MARGIN_PREFIX_RE.sub("", low)
    low = _FOOTNOTE_RE.sub(" ", low).strip()
    low = _TRUNC_SUFFIX_RE.sub("", low).strip()
    low = _TRAIL_PUNCT_RE.sub("", low).strip()
    if low in _PLACEHOLDERS:
        return None
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    try:
        return float(low.replace(",", ""))
    except ValueError:
        return low


def _values_match(a, e) -> bool:
    return _norm(a) == _norm(e)


def _source_fields(expected: dict) -> tuple[set[str], set[str], set, set[str]]:
    sf = expected.get("_source_fields") or {}
    acct = set(sf["account"]) if "account" in sf else set(ACCOUNT_FIELD_MAP.values())
    loc = set(sf["location"]) if "location" in sf else set(LOCATION_FIELD_MAP.values())
    img_locs = set(sf.get("image_only_locations") or [])
    img_fields = set(sf.get("image_only_fields") or [])
    return acct, loc, img_locs, img_fields


def _key(loc: dict):
    n = loc.get("location_number")
    try:
        return int(str(n).strip())
    except (TypeError, ValueError):
        return n


def validate(payload: dict, expected: dict) -> dict:
    """Diff the CU payload against an expected-output JSON. Mirrors
    02_validate_extraction.ipynb output."""
    acct_allowed, loc_allowed, img_locs, img_fields = _source_fields(expected)

    actual_acct = cu_account(payload)
    expected_acct = expected.get("account", {})
    account_diffs = []
    acct_mis_in_src = 0
    for snake in ACCOUNT_FIELD_MAP.values():
        a, e = actual_acct.get(snake), expected_acct.get(snake)
        if a is None and e is None:
            continue
        in_src = snake in acct_allowed
        match = _values_match(a, e)
        if in_src and not match:
            acct_mis_in_src += 1
        account_diffs.append({
            "scope": "account",
            "location_key": None,
            "field": snake,
            "actual": a,
            "expected": e,
            "in_source": in_src,
            "match": match,
        })

    actual_locs = cu_locations(payload)
    expected_locs = expected.get("locations", [])
    a_by = {_key(l): l for l in actual_locs}
    e_by = {_key(l): l for l in expected_locs}
    all_keys: list = sorted(
        set(a_by) | set(e_by), key=lambda x: (x is None, str(x))
    )
    location_diffs = []
    loc_mis_in_src = 0
    for k in all_keys:
        a, e = a_by.get(k, {}), e_by.get(k, {})
        is_image_only = k in img_locs
        for snake in LOCATION_FIELD_MAP.values():
            av, ev = a.get(snake), e.get(snake)
            if av is None and ev is None:
                continue
            in_src = (snake in img_fields) if is_image_only else (snake in loc_allowed)
            match = _values_match(av, ev)
            if in_src and not match:
                loc_mis_in_src += 1
            location_diffs.append({
                "scope": "location",
                "location_key": k,
                "field": snake,
                "actual": av,
                "expected": ev,
                "in_source": in_src,
                "match": match,
            })

    return {
        "summary": {
            "file_name": payload.get("_meta", {}).get("source_file", ""),
            "location_count_actual": len(actual_locs),
            "location_count_expected": len(expected_locs),
            "account_mismatches_in_source": acct_mis_in_src,
            "location_mismatches_in_source": loc_mis_in_src,
        },
        "account": account_diffs,
        "locations": location_diffs,
        "has_ground_truth": True,
    }
