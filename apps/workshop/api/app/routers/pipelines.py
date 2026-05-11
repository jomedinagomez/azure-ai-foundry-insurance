"""Pipeline routes."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services import sov_service
from app.services.pipelines import (
    Pipeline,
    PipelineRunResult,
    StepEvent,
    default_pipeline_for,
    load_pipeline,
    load_pipelines,
    run_pipeline,
    run_pipeline_stream,
)
from app.services.pipelines.library import save_pipeline

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class PipelineRunRequest(BaseModel):
    sample_name: str | None = None
    save_as_canonical: bool = False  # if True, persist payload to cu-output cache


@router.get("")
def list_pipelines_endpoint() -> list[dict]:
    return [p.model_dump() for p in load_pipelines()]


@router.get("/default")
def get_default_pipeline(extension: str) -> dict:
    """`?extension=.xlsx` → the pipeline that's `is_default: true` for that suffix."""
    p = default_pipeline_for(extension)
    if p is None:
        raise HTTPException(404, f"No pipeline accepts extension {extension!r}")
    return p.model_dump()


@router.get("/{pipeline_id}")
def get_pipeline(pipeline_id: str) -> dict:
    p = load_pipeline(pipeline_id)
    if p is None:
        raise HTTPException(404, f"Pipeline not found: {pipeline_id}")
    return p.model_dump()


@router.put("/{pipeline_id}")
def put_pipeline(pipeline_id: str, body: dict[str, Any]) -> dict:
    body = dict(body)
    body["id"] = pipeline_id  # path is authoritative
    pipeline = Pipeline.model_validate(body)
    save_pipeline(pipeline)
    return pipeline.model_dump()


@router.post("/{pipeline_id}/run", response_model=PipelineRunResult)
def run_pipeline_sync(pipeline_id: str, req: PipelineRunRequest) -> PipelineRunResult:
    if not req.sample_name:
        raise HTTPException(400, "sample_name required (use /run/upload for direct file uploads)")
    src = sov_service.ATTACH_DIR / req.sample_name
    if not src.exists():
        raise HTTPException(404, f"Sample not found: {req.sample_name}")
    try:
        result = run_pipeline(pipeline_id, src)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Pipeline run failed: {e}") from e
    if req.save_as_canonical:
        sov_service.save_cached_payload(req.sample_name, result.payload)
    return result


@router.post("/{pipeline_id}/run/upload", response_model=PipelineRunResult)
async def run_pipeline_upload(pipeline_id: str, file: UploadFile = File(...)) -> PipelineRunResult:
    suffix = Path(file.filename or "upload.bin").suffix.lower()
    data = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return run_pipeline(pipeline_id, tmp_path)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Pipeline run failed: {e}") from e
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


@router.post("/{pipeline_id}/run/stream")
def run_pipeline_streaming(pipeline_id: str, req: PipelineRunRequest):
    """Server-Sent Events: one event per step lifecycle. Final event is the
    full payload (event name `complete`)."""
    if not req.sample_name:
        raise HTTPException(400, "sample_name required")
    src = sov_service.ATTACH_DIR / req.sample_name
    if not src.exists():
        raise HTTPException(404, f"Sample not found: {req.sample_name}")

    save_canonical = bool(req.save_as_canonical)
    sample_name = req.sample_name

    def _gen():
        try:
            for item in run_pipeline_stream(pipeline_id, src):
                if isinstance(item, StepEvent):
                    yield f"event: step\ndata: {item.model_dump_json()}\n\n"
                elif isinstance(item, PipelineRunResult):
                    if save_canonical:
                        try:
                            sov_service.save_cached_payload(sample_name, item.payload)
                        except Exception:
                            pass
                    yield f"event: complete\ndata: {item.model_dump_json()}\n\n"
        except Exception as e:
            err = {"error": str(e)[:500]}
            yield f"event: error\ndata: {json.dumps(err)}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")
