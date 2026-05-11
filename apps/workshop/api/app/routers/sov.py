"""SOV extraction + validation endpoints."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.schemas.sov import (
    SovExtractionResult,
    SovExtractRequest,
    SovSample,
    SovValidationResult,
)
from app.services import sov_service
from app.services.pipelines import default_pipeline_for, run_pipeline

router = APIRouter(prefix="/sov", tags=["sov"])


class SovPipelineRunRequest(BaseModel):
    sample_name: str
    pipeline_id: Optional[str] = None  # None -> auto-pick by extension
    save_as_canonical: bool = False


@router.post("/extract/pipeline", response_model=SovExtractionResult)
def run_pipeline_for_sample(req: SovPipelineRunRequest):
    """Run the chosen pipeline (or the extension default) for a known sample
    and return the same SovExtractionResult shape the SOV tab consumes.

    This is the bridge between the new pipelines machinery and the existing
    SovPage UI, so the page doesn't have to know about CU payload internals."""
    src = sov_service.ATTACH_DIR / req.sample_name
    if not src.exists():
        raise HTTPException(status_code=404, detail=f"Sample not found: {req.sample_name}")

    pipeline_id = req.pipeline_id
    if not pipeline_id:
        ext = src.suffix.lower()
        p = default_pipeline_for(ext)
        if p is None:
            raise HTTPException(status_code=404, detail=f"No pipeline for extension {ext!r}")
        pipeline_id = p.id

    try:
        result = run_pipeline(pipeline_id, src)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline run failed: {e}") from e

    payload = result.payload
    payload.setdefault("_meta", {})["source_file"] = req.sample_name

    if req.save_as_canonical:
        sov_service.save_cached_payload(req.sample_name, payload)

    return sov_service.project_result(payload)


@router.get("/samples", response_model=list[SovSample])
def list_samples():
    return sov_service.list_samples()


@router.get("/samples/{name}/cached")
def get_cached(name: str):
    payload = sov_service.get_cached_payload(name)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No cached result for {name}")
    return sov_service.project_result(payload)


@router.post("/extract", response_model=SovExtractionResult)
def extract(req: SovExtractRequest):
    try:
        payload = sov_service.analyze_sample(
            req.sample_name, force_refresh=req.force_refresh, pattern=req.pattern
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}") from e
    return sov_service.project_result(payload)


@router.post("/save-cache")
def save_cache(body: dict[str, Any]):
    """Persist a payload (typically a non-Auto run) as the canonical cached
    result for a sample, so subsequent validate calls use it.
    Body: {sample_name: str, payload: dict}."""
    name = body.get("sample_name")
    payload = body.get("payload")
    if not name or not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="sample_name and payload required")
    try:
        sov_service.save_cached_payload(name, payload)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"status": "saved", "sample_name": name}


@router.post("/extract/upload", response_model=SovExtractionResult)
async def extract_upload(file: UploadFile = File(...)):
    try:
        data = await file.read()
        payload = sov_service.analyze_uploaded(data, file.filename or "upload.bin")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}") from e
    return sov_service.project_result(payload)


@router.get("/expected/{name}")
def get_expected(name: str):
    expected = sov_service.get_expected(name)
    if expected is None:
        raise HTTPException(status_code=404, detail=f"No ground truth for {name}")
    return expected


@router.post("/validate", response_model=SovValidationResult)
def validate(req: SovExtractRequest):
    """Validate extraction (cached or freshly run) against ground truth."""
    expected = sov_service.get_expected(req.sample_name)
    if expected is None:
        raise HTTPException(
            status_code=404,
            detail=f"No ground truth for {req.sample_name}",
        )
    payload = sov_service.get_cached_payload(req.sample_name)
    if payload is None or req.force_refresh:
        try:
            payload = sov_service.analyze_sample(req.sample_name, force_refresh=req.force_refresh)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Extraction failed: {e}") from e
    return sov_service.validate(payload, expected)


# ── Analyzer template management ────────────────────────────────────────────
@router.get("/analyzers")
def list_analyzers():
    return sov_service.list_analyzers()


@router.get("/analyzers/{template_file}")
def get_analyzer_template(template_file: str):
    try:
        return sov_service.get_analyzer_template(template_file)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/analyzers/{template_file}")
def save_analyzer_template(template_file: str, body: dict[str, Any]):
    try:
        sov_service.save_analyzer_template(template_file, body)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "saved", "template_file": template_file}


@router.post("/analyzers/{template_file}/push")
def push_analyzer(template_file: str, analyzer_id: str):
    try:
        return sov_service.push_analyzer_to_foundry(analyzer_id, template_file)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Push failed: {e}") from e


# ── Pattern config ──────────────────────────────────────────────────────────
@router.get("/patterns")
def get_patterns():
    return sov_service.get_pattern_config()


class PatternUpdate(dict):
    pass


@router.put("/patterns/{pattern}")
def update_pattern(pattern: str, body: dict[str, str]):
    analyzer_id = body.get("analyzer_id")
    template_file = body.get("template_file")
    if not analyzer_id or not template_file:
        raise HTTPException(status_code=400, detail="analyzer_id and template_file required")
    try:
        return sov_service.set_pattern_config(pattern, analyzer_id, template_file)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
