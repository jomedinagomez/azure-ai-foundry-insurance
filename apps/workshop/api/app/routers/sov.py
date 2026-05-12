"""SOV extraction + validation endpoints."""
from __future__ import annotations

import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.schemas.sov import (
    SovExtractionResult,
    SovExtractRequest,
    SovSample,
    SovValidationResult,
)
from app.services import sov_service
from app.services import cost
from app.services.pipelines import (
    PipelineRunResult,
    StepEvent,
    default_pipeline_for,
    run_pipeline,
    run_pipeline_stream,
)

router = APIRouter(prefix="/sov", tags=["sov"])

# Persistent per-run artifact dir (xlsx → pdf → tiff debugging)
RUNS_DIR = Path(__file__).resolve().parents[2] / ".runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _new_run_dir(sample_name: str, pipeline_id: str) -> tuple[str, Path]:
    stem = Path(sample_name).stem
    run_id = f"{stem}__{pipeline_id}__{int(time.time())}_{uuid.uuid4().hex[:6]}"
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return run_id, d


def _to_artifact_urls(run_id: str, artifacts: dict[str, str], work_dir: Path) -> dict[str, str]:
    """Replace local paths in `artifacts` with download URLs.

    Files under `work_dir` are served via `/sov/runs/{run_id}/artifacts/...`.
    Files under the samples dir (e.g. the unmodified input PDF that the
    pipeline analyzed directly) are served via `/sov/samples/{name}/raw`
    so the frontend can preview them in the visualizer."""
    out: dict[str, str] = {}
    work_resolved = work_dir.resolve()
    attach_resolved = sov_service.ATTACH_DIR.resolve()
    for k, p in artifacts.items():
        try:
            full = Path(p).resolve()
        except OSError:
            out[k] = p
            continue
        try:
            full.relative_to(work_resolved)
            out[k] = f"/sov/runs/{run_id}/artifacts/{full.name}"
            continue
        except ValueError:
            pass
        try:
            full.relative_to(attach_resolved)
            out[k] = f"/sov/samples/{full.name}/raw"
            continue
        except ValueError:
            pass
        out[k] = p
    return out



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

    run_id, work_dir = _new_run_dir(req.sample_name, pipeline_id)
    try:
        result = run_pipeline(pipeline_id, src, work_dir=work_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline run failed: {e}") from e

    payload = result.payload
    payload.setdefault("_meta", {})["source_file"] = req.sample_name
    # Rewrite artifact paths in meta to download URLs
    artifacts_urls = _to_artifact_urls(run_id, result.artifacts, work_dir)
    payload["_meta"]["pipeline_artifacts"] = artifacts_urls
    payload["_meta"]["run_id"] = run_id
    # Estimated cost — driven entirely by the `usage` block CU returns.
    payload["_meta"]["cost"] = cost.estimate_pipeline_cost(payload)

    if req.save_as_canonical:
        sov_service.save_cached_payload(req.sample_name, payload)

    return sov_service.project_result(payload)


@router.post("/extract/pipeline/stream")
def run_pipeline_for_sample_stream(req: SovPipelineRunRequest):
    """Streaming variant of `/extract/pipeline` (Server-Sent Events).

    Emits one `step` event per pipeline step lifecycle, then a single
    `complete` event whose `data` is the projected `SovExtractionResult`
    (same shape the SOV tab consumes), wrapped in a small envelope:

        { "result": <SovExtractionResult>, "timings": {...}, "artifacts": {...} }

    The envelope keeps `timings` available for the RunDialog's "total time"
    readout while letting the SOV tab consume `result` directly."""
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

    save_canonical = bool(req.save_as_canonical)
    sample_name = req.sample_name
    run_id, work_dir = _new_run_dir(sample_name, pipeline_id)

    def _gen():
        try:
            for item in run_pipeline_stream(pipeline_id, src, work_dir=work_dir):
                if isinstance(item, StepEvent):
                    yield f"event: step\ndata: {item.model_dump_json()}\n\n"
                elif isinstance(item, PipelineRunResult):
                    payload = item.payload
                    payload.setdefault("_meta", {})["source_file"] = sample_name
                    artifacts_urls = _to_artifact_urls(run_id, item.artifacts, work_dir)
                    payload["_meta"]["pipeline_artifacts"] = artifacts_urls
                    payload["_meta"]["run_id"] = run_id
                    payload["_meta"]["cost"] = cost.estimate_pipeline_cost(payload)
                    if save_canonical:
                        try:
                            sov_service.save_cached_payload(sample_name, payload)
                        except Exception:
                            pass
                    projected = sov_service.project_result(payload)
                    envelope = {
                        "result": projected,
                        "timings": item.timings,
                        "artifacts": artifacts_urls,
                        "run_id": run_id,
                    }
                    yield f"event: complete\ndata: {json.dumps(envelope)}\n\n"
        except Exception as e:
            err = {"error": str(e)[:500]}
            yield f"event: error\ndata: {json.dumps(err)}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@router.get("/runs/{run_id}/artifacts/{filename}")
def download_artifact(
    run_id: str,
    filename: str,
    as_: Optional[str] = Query(None, alias="as"),
    page: int = 0,
    trim: int = 1,
    max_dim: int = 2400,
):
    """Serve a single artifact file from a previous pipeline run.

    Optional transcoding for browser preview:
    - `?as=png` on a `.tiff` returns a PNG preview of `?page=N` (0-indexed,
      default 0). Browsers don't render TIFF natively, so the SovPage Image
      tab uses this to show what CU actually saw.
    - `?trim=1` (default) crops white margins so cascade-style layouts that
      only fill the left half of the page don't waste real estate.
    - `?max_dim=2400` downsamples the longest side to keep transfer < ~2 MB.
    """
    safe_run = Path(run_id).name
    safe_file = Path(filename).name
    target = (RUNS_DIR / safe_run / safe_file).resolve()
    try:
        target.relative_to(RUNS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    if as_ == "png" and target.suffix.lower() in (".tif", ".tiff"):
        try:
            png_path = _tiff_page_to_png(
                target, page=page, trim=bool(trim), max_dim=max_dim
            )
        except IndexError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Transcode failed: {e}") from e
        return FileResponse(
            path=str(png_path),
            media_type="image/png",
            filename=png_path.name,
        )

    media_type, _ = mimetypes.guess_type(target.name)
    return FileResponse(
        path=str(target),
        media_type=media_type or "application/octet-stream",
        filename=target.name,
    )


@router.get("/runs/{run_id}/artifacts/{filename}/info")
def artifact_info(run_id: str, filename: str):
    """Return basic metadata for an artifact (page count for TIFFs).

    Used by the SovPage Image preview to render page navigation when the
    rendered TIFF has more than one page."""
    safe_run = Path(run_id).name
    safe_file = Path(filename).name
    target = (RUNS_DIR / safe_run / safe_file).resolve()
    try:
        target.relative_to(RUNS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    info: dict[str, Any] = {
        "name": target.name,
        "size": target.stat().st_size,
        "suffix": target.suffix.lower(),
        "pages": 1,
    }
    if target.suffix.lower() in (".tif", ".tiff"):
        try:
            from PIL import Image

            with Image.open(target) as im:
                info["pages"] = getattr(im, "n_frames", 1)
                # Per-page native dimensions in pixels — needed by the frontend
                # overlay so CU polygon coords (also in source pixels) can be
                # mapped onto the rendered preview, which may be trimmed/resized.
                dims: list[dict[str, int]] = []
                for i in range(info["pages"]):
                    im.seek(i)
                    dims.append({"width": im.width, "height": im.height})
                info["page_dimensions"] = dims
        except Exception:
            pass
    return info


def _tiff_page_to_png(
    tiff_path: Path,
    *,
    page: int = 0,
    trim: bool = True,
    max_dim: int = 2400,
) -> Path:
    """Render one page of a TIFF to a cached PNG (browser-friendly preview).

    Caches under the same dir as the source so repeat requests are O(1)
    file-server lookups, not full re-decodes."""
    from PIL import Image

    cache_name = f"{tiff_path.stem}.page{page}{'.trim' if trim else ''}.max{max_dim}.png"
    cache = tiff_path.with_name(cache_name)
    if cache.exists():
        return cache

    with Image.open(tiff_path) as im:
        n_frames = getattr(im, "n_frames", 1)
        if page < 0 or page >= n_frames:
            raise IndexError(f"page {page} out of range (0..{n_frames - 1})")
        im.seek(page)
        img = im.convert("RGB")

    if trim:
        # Threshold to identify content (anything darker than near-white).
        gray = img.convert("L")
        mask = gray.point(lambda v: 0 if v >= 248 else 255)
        bbox = mask.getbbox()
        if bbox is not None:
            pad = 24
            l = max(0, bbox[0] - pad)
            t = max(0, bbox[1] - pad)
            r = min(img.width, bbox[2] + pad)
            b = min(img.height, bbox[3] + pad)
            img = img.crop((l, t, r, b))

    if max(img.width, img.height) > max_dim:
        ratio = max_dim / max(img.width, img.height)
        new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    img.save(cache, "PNG", optimize=True)
    return cache


@router.get("/samples", response_model=list[SovSample])
def list_samples():
    return sov_service.list_samples()


@router.get("/samples/{name}/cached")
def get_cached(name: str):
    payload = sov_service.get_cached_payload(name)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No cached result for {name}")
    projected = sov_service.project_result(payload)
    # Cached CU payloads have no pipeline run attached, so the visualizer
    # would render an empty state. Synthesize a `pipeline_artifacts.input`
    # entry pointing at the raw sample so the preview pane still works
    # (and the user can review the file the analyzer received).
    meta = projected.setdefault("meta", {})
    artifacts = meta.get("pipeline_artifacts") or {}
    if "input" not in artifacts:
        artifacts["input"] = f"/sov/samples/{name}/raw"
        meta["pipeline_artifacts"] = artifacts
    # Always recompute cost from the saved CU payload. Cached files may
    # have been written by an older cost model; recomputing keeps the
    # breakdown consistent with the current pricing.json + cost.py. If the
    # saved payload predates `usage` capture, drop the cost so the UI
    # doesn't show misleading partial numbers — the user can re-run to
    # populate it.
    if isinstance(payload.get("usage"), dict):
        meta["cost"] = cost.estimate_pipeline_cost(payload)
    else:
        meta.pop("cost", None)
    return projected


@router.get("/samples/{name}/raw")
def get_sample_raw(name: str):
    """Stream the original sample file (PDF / XLSX) to the browser.

    Used by the SovPage visualizer to show the input PDF as the
    "artifact sent to CU" when the pipeline has no intermediate
    rasterization (e.g. `pdf_extract` analyzes the source PDF directly)."""
    safe = Path(name).name
    target = (sov_service.ATTACH_DIR / safe).resolve()
    try:
        target.relative_to(sov_service.ATTACH_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Sample not found: {name}")
    media_type, _ = mimetypes.guess_type(target.name)
    # Force inline disposition so PDFs render in the iframe instead of
    # downloading. FileResponse's `filename=` kwarg sets
    # `Content-Disposition: attachment`, which is the opposite of what we want.
    return FileResponse(
        path=str(target),
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{target.name}"'},
    )


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
