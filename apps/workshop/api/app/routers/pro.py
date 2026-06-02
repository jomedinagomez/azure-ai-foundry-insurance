"""Pro Mode router — Claims + Fraud Detection demos.

Endpoints:
- GET    /pro/healthcheck                       — endpoint config + analyzer presence
- GET    /pro/samples                           — list bundled sample claim packages
- GET    /pro/samples/{id}/files/{name}         — download a single sample input file
- POST   /pro/samples/{id}/analyze?scenario=    — one-click analyze a bundled sample
- POST   /pro/claims/analyze                    — analyze user-uploaded files (claims)
- POST   /pro/fraud/analyze                     — analyze user-uploaded files (fraud)
- POST   /pro/deploy                            — deploy/refresh both pro analyzers
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.schemas.pro import (
    ProClaimsResult,
    ProFraudResult,
    ProHealthcheck,
    ProSampleManifest,
)
from app.services import pro_service

router = APIRouter(prefix="/pro", tags=["pro"])


@router.get("/healthcheck", response_model=ProHealthcheck)
def healthcheck() -> ProHealthcheck:
    info = pro_service.healthcheck()
    return ProHealthcheck(**info)


@router.get("/samples", response_model=list[ProSampleManifest])
def list_samples() -> list[ProSampleManifest]:
    return pro_service.list_sample_manifests()


@router.get("/samples/{sample_id}/files/{file_name}")
def get_sample_file(sample_id: str, file_name: str):
    folder = pro_service.SAMPLES_DIR / sample_id
    safe = (folder / Path(file_name).name).resolve()
    try:
        safe.relative_to(folder.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not safe.exists() or not safe.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    media, _ = mimetypes.guess_type(safe.name)
    return FileResponse(str(safe), media_type=media or "application/octet-stream", filename=safe.name)


@router.post("/deploy")
def deploy(overwrite: bool = Query(False)):
    """Deploy (or refresh) both pro-mode analyzers."""
    try:
        return pro_service.deploy_all(overwrite=overwrite)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deploy failed: {e}") from e


@router.post("/samples/{sample_id}/analyze")
def analyze_sample(
    sample_id: str,
    scenario: Literal["claims", "fraud"] = Query(...),
):
    try:
        manifest, files = pro_service.load_sample(sample_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    try:
        if scenario == "claims":
            return pro_service.analyze_claims(files, sample_id=sample_id)
        return pro_service.analyze_fraud(files, sample_id=sample_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analyze failed: {e}") from e


def _persist_uploads(uploads: list[UploadFile]) -> list[Path]:
    import tempfile
    out: list[Path] = []
    tmp_root = Path(tempfile.mkdtemp(prefix="pro_upload_"))
    for u in uploads:
        target = tmp_root / Path(u.filename or "upload.bin").name
        with target.open("wb") as f:
            f.write(u.file.read())
        out.append(target)
    return out


@router.post("/claims/analyze", response_model=ProClaimsResult)
def analyze_claims_upload(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file required.")
    paths = _persist_uploads(files)
    try:
        return pro_service.analyze_claims(paths)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analyze failed: {e}") from e


@router.post("/fraud/analyze", response_model=ProFraudResult)
def analyze_fraud_upload(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file required.")
    paths = _persist_uploads(files)
    try:
        return pro_service.analyze_fraud(paths)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analyze failed: {e}") from e
