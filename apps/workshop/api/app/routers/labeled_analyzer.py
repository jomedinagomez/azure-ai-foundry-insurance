"""Cached and live comparison endpoints for the labeled analyzer demo."""
from __future__ import annotations

import json
import mimetypes
import os
import threading
import time

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.schemas.labeled_analyzer import (
    AutoLabelRequest,
    DocumentLabelsUpdate,
    LabelingProjectCreate,
    LabeledAnalyzerSample,
    LabeledAnalyzerStatus,
    LabeledEvaluationRequest,
)
from app.services import labeled_analyzer_service as service
from app.services import labeling_workspace_service as workspace
from app.services.cu_errors import friendly_cu_error


router = APIRouter(prefix="/labeled-analyzer", tags=["labeled-analyzer"])
_LIVE_LOCK = threading.Lock()
_LAST_LIVE_STARTED = 0.0


def _live_enabled() -> bool:
    return os.environ.get("LABELED_ANALYZER_ENABLE_LIVE", "false").casefold() == "true"


def _is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


def _require_loopback(request: Request) -> None:
    if not _is_loopback(request):
        raise HTTPException(status_code=403, detail="Authoring is restricted to loopback clients.")


@router.get("/status", response_model=LabeledAnalyzerStatus)
def status():
    endpoint = (
        os.environ.get("APP_CONTENT_UNDERSTANDING_ENDPOINT")
        or os.environ.get("CONTENTUNDERSTANDING_ENDPOINT")
        or os.environ.get("FOUNDRY_ENDPOINT")
    )
    storage = os.environ.get("LABELED_ANALYZER_STORAGE_ACCOUNT") or os.environ.get(
        "STORAGE_ACCOUNT_NAME"
    )
    return {
        "api_version": service.API_VERSION,
        "model": "gpt-5.2",
        "embedding_model": "text-embedding-3-large",
        "training_files": list(service.TRAINING_FILES),
        "holdout_files": list(service.HOLDOUT_FILES),
        "labeled_data": service.labeled_data_status(),
        "cached_report": _has_current_report(),
        "live_endpoint_configured": bool(endpoint),
        "live_evaluation_enabled": _live_enabled(),
        "storage_configured": bool(storage),
        "analyzer_ids": {
            "zero_shot": service.ZERO_SHOT_ANALYZER_ID,
            "labeled": service.LABELED_ANALYZER_ID,
        },
    }


@router.get("/workspace/status")
def workspace_status():
    return workspace.workspace_capabilities()


@router.get("/projects")
def projects(request: Request):
    _require_loopback(request)
    return workspace.list_projects()


@router.post("/projects", status_code=201)
def create_project(body: LabelingProjectCreate, request: Request):
    _require_loopback(request)
    try:
        return workspace.create_project(name=body.name, analyzer_id=body.analyzer_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{project_id}")
def project(project_id: str, request: Request):
    _require_loopback(request)
    try:
        return workspace.get_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/documents", status_code=201)
async def upload_documents(
    project_id: str,
    request: Request,
    role: str = Form(...),
    files: list[UploadFile] = File(...),
):
    _require_loopback(request)
    try:
        uploads = []
        for file in files:
            data = await file.read(workspace.MAX_DOCUMENT_BYTES + 1)
            uploads.append((file.filename or "", data, file.content_type))
        return workspace.add_documents(project_id, uploads, role=role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/documents/{document_id}")
def document(project_id: str, document_id: str, request: Request):
    _require_loopback(request)
    try:
        return workspace.load_document(project_id, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/documents/{document_id}/file")
def document_file(project_id: str, document_id: str, request: Request):
    _require_loopback(request)
    try:
        path = workspace.source_path(project_id, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="application/pdf")


@router.put("/projects/{project_id}/documents/{document_id}/labels")
def update_document_labels(
    project_id: str,
    document_id: str,
    body: DocumentLabelsUpdate,
    request: Request,
):
    _require_loopback(request)
    try:
        return workspace.save_document_labels(
            project_id,
            document_id,
            {name: value.model_dump() for name, value in body.labels.items()},
            reviewed=body.reviewed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/analyzers/base")
def create_project_analyzer(project_id: str, request: Request):
    _require_loopback(request)
    try:
        return workspace.create_base_analyzer(project_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/documents/{document_id}/autolabel")
def auto_label_document(
    project_id: str,
    document_id: str,
    body: AutoLabelRequest,
    request: Request,
):
    _require_loopback(request)
    try:
        return workspace.auto_label_document(
            project_id,
            document_id,
            analyzer_id=body.analyzer_id,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/documents/{document_id}/prepare")
def prepare_document(project_id: str, document_id: str, request: Request):
    _require_loopback(request)
    try:
        return workspace.prepare_document_for_manual_labeling(project_id, document_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/export")
def export_project(project_id: str, request: Request):
    _require_loopback(request)
    try:
        file_name, content = workspace.export_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.post("/projects/{project_id}/analyzers/trained")
def create_trained_analyzer(project_id: str, request: Request):
    _require_loopback(request)
    try:
        return workspace.build_trained_analyzer(project_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/score")
def score_project(project_id: str, request: Request):
    _require_loopback(request)
    try:
        return workspace.score_project(project_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/samples", response_model=list[LabeledAnalyzerSample])
def samples():
    truth = service.load_ground_truth()["documents"]
    return [
        {
            "file_name": file_name,
            "size_kb": round(service.assert_holdout_file(file_name).stat().st_size / 1024, 1),
            "challenge": truth[file_name]["challenge"],
            "has_ground_truth": True,
            "has_zero_shot_cache": service.cache_path(file_name, "zero_shot").is_file(),
            "has_labeled_cache": service.cache_path(file_name, "labeled").is_file(),
        }
        for file_name in service.HOLDOUT_FILES
    ]


@router.get("/samples/{file_name}/raw")
def sample_pdf(file_name: str):
    try:
        path = service.assert_holdout_file(file_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    media_type = mimetypes.guess_type(path.name)[0] or "application/pdf"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.get("/report")
def report():
    try:
        payload = service.load_valid_report()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="No cached evaluation report. Run the build/evaluation notebook first.",
        )
    return payload


@router.post("/evaluate/stream")
def evaluate_stream(body: LabeledEvaluationRequest, request: Request):
    global _LAST_LIVE_STARTED
    try:
        selected = service.resolve_holdouts(body.sample_names)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    live_slot = False
    if body.force_live:
        if not _live_enabled():
            raise HTTPException(
                status_code=403,
                detail="Live labeled evaluation is disabled. Set LABELED_ANALYZER_ENABLE_LIVE=true for local use.",
            )
        if not _is_loopback(request):
            raise HTTPException(status_code=403, detail="Live evaluation is restricted to loopback clients.")
        if not _LIVE_LOCK.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="A live evaluation is already running.")
        live_slot = True
        minimum_interval = float(os.environ.get("LABELED_ANALYZER_LIVE_COOLDOWN_SECONDS", "30"))
        now = time.monotonic()
        if now - _LAST_LIVE_STARTED < minimum_interval:
            _LIVE_LOCK.release()
            retry_after = round(minimum_interval - (now - _LAST_LIVE_STARTED), 1)
            raise HTTPException(status_code=429, detail=f"Wait {retry_after}s before another live evaluation.")
        _LAST_LIVE_STARTED = now

    def generate():
        try:
            if not body.force_live:
                yield _event("step", {"step_id": "load_report", "status": "running"})
                cached = service.load_valid_report()
                if cached is None:
                    raise FileNotFoundError(
                        "No cached report is available. Run the build/evaluation notebook or choose live evaluation."
                    )
                service.validate_cached_report(
                    cached,
                    sample_names=selected,
                    repeats=body.repeats,
                )
                yield _event("step", {"step_id": "load_report", "status": "done"})
                yield _event("complete", cached)
                return

            for event_name, data in service.evaluation_events(
                repeats=body.repeats,
                use_cache=False,
                sample_names=selected,
            ):
                yield _event(event_name, data)
        except Exception as exc:
            friendly = friendly_cu_error(exc)
            message = friendly or f"{type(exc).__name__}: {str(exc)[:400]}"
            yield _event("error", {"error": message})
        finally:
            if live_slot:
                _LIVE_LOCK.release()

    return StreamingResponse(generate(), media_type="text/event-stream")


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


def _has_current_report() -> bool:
    try:
        return service.load_valid_report() is not None
    except (FileNotFoundError, ValueError):
        return False