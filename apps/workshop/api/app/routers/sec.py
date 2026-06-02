"""SEC financial-table extraction endpoints.

Thin wrapper around `app.services.sec_service`. The notebooks under
`demo/sec/notebooks/` call into the same service module so behavior is
always identical between the API/UI and the workshop notebooks.
"""
from __future__ import annotations

import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.schemas.sec import (
    SecExtractionResult,
    SecExtractRequest,
    SecSample,
    SecValidationResult,
)
from app.services import cost, sec_service

router = APIRouter(prefix="/sec", tags=["sec"])

# Persistent per-run artifact dir (xlsx exports)
RUNS_DIR = Path(__file__).resolve().parents[2] / ".runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _new_run_dir(sample_name: str) -> tuple[str, Path]:
    stem = Path(sample_name).stem
    run_id = f"{stem}__sec__{int(time.time())}_{uuid.uuid4().hex[:6]}"
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return run_id, d


@router.get("/samples", response_model=list[SecSample])
def list_samples():
    return sec_service.list_samples()


@router.get("/samples/{file_name}/raw")
def download_sample(file_name: str):
    p = sec_service.ATTACH_DIR / file_name
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Sample not found: {file_name}")
    media = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return FileResponse(p, media_type=media, filename=p.name)


@router.post("/redeploy-analyzers")
def redeploy_analyzers():
    """Force-replace the SEC analyzer + classifier on the Content Understanding
    resource. Use this after changing model deployments in .env so the
    classifier picks up the new completion/embedding model wiring."""
    try:
        statuses = sec_service.ensure_analyzers(force_replace=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redeploy failed: {e}") from e
    return {"statuses": statuses}


@router.post("/extract", response_model=SecExtractionResult)
def extract(req: SecExtractRequest):
    """Run end-to-end SEC extraction for a known sample.

    With `use_cache=true` (default) and a cached payload present, returns
    instantly without any Azure call — useful for offline demos. Otherwise
    calls Content Understanding (deploying analyzers on first use).
    """
    src = sec_service.ATTACH_DIR / req.sample_name
    if not src.exists():
        raise HTTPException(status_code=404, detail=f"Sample not found: {req.sample_name}")

    run_id, work_dir = _new_run_dir(req.sample_name)
    excel_out = work_dir / f"{Path(req.sample_name).stem}.xlsx"

    try:
        # Ensure analyzers exist on first uncached run.
        if not req.use_cache or sec_service.load_cached_payload(req.sample_name) is None:
            try:
                sec_service.ensure_analyzers()
            except Exception as e:
                # Surface but don't block — caller may still get cached data.
                raise HTTPException(
                    status_code=500,
                    detail=f"Analyzer deploy failed: {e}",
                ) from e
        result = sec_service.run_extraction(
            req.sample_name,
            use_cache=req.use_cache,
            save_as_canonical=req.save_as_canonical,
            excel_out=excel_out,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}") from e

    # Rewrite local excel path to a download URL.
    if excel_out.exists():
        result["meta"]["run_id"] = run_id
        result["meta"]["artifacts"] = {
            "excel": f"/sec/runs/{run_id}/artifacts/{excel_out.name}"
        }
    return result


@router.post("/extract/stream")
def extract_stream(req: SecExtractRequest):
    """SSE variant of /extract. Emits coarse step events:
      step: deploy_analyzers, cu_classify_and_extract, merge_segments, excel_export
      complete: { result: SecExtractionResult }
    """
    src = sec_service.ATTACH_DIR / req.sample_name
    if not src.exists():
        raise HTTPException(status_code=404, detail=f"Sample not found: {req.sample_name}")

    run_id, work_dir = _new_run_dir(req.sample_name)
    excel_out = work_dir / f"{Path(req.sample_name).stem}.xlsx"
    sample_name = req.sample_name
    use_cache = req.use_cache
    save_canonical = req.save_as_canonical

    def _emit(step_id: str, status: str, **meta) -> str:
        evt = {"step_id": step_id, "status": status, **meta}
        return f"event: step\ndata: {json.dumps(evt)}\n\n"

    def _gen():
        try:
            from_cache = False
            t0 = time.time()
            merged = None
            retries = 0
            raw = None

            if use_cache:
                yield _emit("load_cache", "running")
                cached = sec_service.load_cached_payload(sample_name)
                if cached is not None:
                    contents = cached.get("contents") or []
                    has_segments = any("category" in (c or {}) for c in contents)
                    if has_segments:
                        raw = cached
                        merged = sec_service.merge_segments(cached)
                    else:
                        merged = cached  # legacy flat cache; no page metadata
                    from_cache = True
                yield _emit("load_cache", "done", from_cache=from_cache)

            if not from_cache:
                yield _emit("deploy_analyzers", "running")
                statuses = sec_service.ensure_analyzers()
                yield _emit("deploy_analyzers", "done", statuses=statuses)

                yield _emit("cu_classify_and_extract", "running")
                pdf_bytes = (sec_service.ATTACH_DIR / sample_name).read_bytes()
                raw, retries = sec_service.classify_and_extract(pdf_bytes)
                seg_counts = sec_service.segment_category_counts(raw)
                yield _emit(
                    "cu_classify_and_extract",
                    "done",
                    retries=retries,
                    segment_categories=seg_counts,
                )

                yield _emit("merge_segments", "running")
                merged = sec_service.merge_segments(raw)
                if save_canonical:
                    # Persist raw so future loads can recover per-segment page metadata.
                    sec_service.save_cached_payload(sample_name, raw)
                yield _emit("merge_segments", "done")

            yield _emit("excel_export", "running")
            sec_service.export_to_excel(merged, excel_out)
            yield _emit("excel_export", "done", file=excel_out.name)

            elapsed = time.time() - t0
            meta_extra = {
                "elapsed_sec": round(elapsed, 2),
                "retries": retries,
                "segment_categories": sec_service.segment_category_counts(raw) if raw else {},
                "missing_statements": sec_service.missing_categories(raw) if raw else [],
                "from_cache": from_cache,
                "run_id": run_id,
                "artifacts": {"excel": f"/sec/runs/{run_id}/artifacts/{excel_out.name}"},
                "cost": cost.estimate_cu_cost(merged) if merged.get("usage") else {},
            }
            projected = sec_service.project_result(
                merged, file_name=sample_name, meta_extra=meta_extra
            )
            envelope = {"result": projected, "run_id": run_id}
            yield f"event: complete\ndata: {json.dumps(envelope)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)[:500]})}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.get("/runs/{run_id}/artifacts/{filename}")
def download_artifact(run_id: str, filename: str):
    p = RUNS_DIR / run_id / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    media = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return FileResponse(p, media_type=media, filename=p.name)


class SecValidateRequest(BaseModel):
    result: dict


@router.post("/validate", response_model=SecValidationResult)
def validate(req: SecValidateRequest):
    return sec_service.validate(req.result)


class SecSaveExpectedRequest(BaseModel):
    result: dict


@router.post("/save-expected")
def save_expected(req: SecSaveExpectedRequest):
    """Write the line-item shell of a result as the ground-truth file for its
    sample. The next /sec/validate call will compare against this file."""
    try:
        out_path = sec_service.save_as_expected(req.result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    rel = out_path.relative_to(sec_service.SEC_DEMO_ROOT.parent.parent)
    return {"written": str(rel).replace("\\", "/"), "bytes": out_path.stat().st_size}
