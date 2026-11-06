"""Claims Explorer: local evidence reads and explicit Azure processing."""
import logging
import mimetypes
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.services import claims_service as service
from app.services.cu_errors import friendly_cu_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/claims", tags=["claims"])
T = TypeVar("T")


def _call(action: Callable[[], T]) -> T:
    try:
        return action()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, KeyError) as exc:
        logger.warning("Claims request rejected: %s", exc)
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        logger.warning("Claims operation unavailable: %s", exc)
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        logger.exception("Claims operation failed")
        raise HTTPException(502, friendly_cu_error(exc) or str(exc)) from exc


class RunRequest(BaseModel):
    claim_ids: list[str] = Field(min_length=1, max_length=50)
    index_data: bool = False
    document_image_names: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=24000)


@router.get("")
def list_claims() -> dict[str, Any]:
    return _call(service.list_claims)


@router.get("/run")
def active_run() -> dict[str, Any] | None:
    return _call(service.active_job)


@router.post("/run", status_code=202)
def run_claims(request: RunRequest) -> dict[str, Any]:
    return _call(lambda: service.start_run(request.claim_ids, request.index_data, set(request.document_image_names)))


@router.get("/{claim_id}")
def claim_detail(claim_id: str) -> dict[str, Any]:
    return _call(lambda: service.claim_detail(claim_id))


@router.get("/{claim_id}/files/{evidence_id}")
def file_detail(claim_id: str, evidence_id: str) -> dict[str, Any]:
    return _call(lambda: service.file_detail(claim_id, evidence_id))


@router.get("/{claim_id}/files/{evidence_id}/raw")
def raw_file(claim_id: str, evidence_id: str) -> Response:
    item = _call(lambda: service.raw_file(claim_id, evidence_id))
    return Response(content=item.data, media_type=mimetypes.guess_type(item.filename)[0] or "application/octet-stream",
                    headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.post("/{claim_id}/search")
def search_claim(claim_id: str, request: SearchRequest) -> list[dict[str, Any]]:
    return _call(lambda: service.search(claim_id, request.question))
