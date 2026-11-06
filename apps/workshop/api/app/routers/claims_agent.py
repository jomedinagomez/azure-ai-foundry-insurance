"""Local agent controls. GETs never create a remote agent or invoke a model."""
import logging
from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import claims_agent_service as service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/claims-agent", tags=["claims-agent"])
T = TypeVar("T")


def _call(action: Callable[[], T]) -> T:
    try:
        return action()
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        logger.warning("Claims agent request rejected: %s", exc)
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        logger.warning("Claims agent unavailable: %s", exc)
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        logger.exception("Claims agent operation failed")
        raise HTTPException(502, str(exc)) from exc


class ConversationRequest(BaseModel):
    claim_id: str = Field(pattern=r"^claim-\d{3}$")


class MessageRequest(BaseModel):
    question: str = Field(min_length=1, max_length=16000)


@router.get("/status")
def status():
    return _call(service.status)


@router.post("/register")
def register():
    """Explicit metadata-only Foundry external-agent version creation."""
    return _call(service.register)


@router.get("/conversations")
def conversations(claim_id: str = Query(pattern=r"^claim-\d{3}$")):
    return _call(lambda: service.list_conversations(claim_id))


@router.post("/conversations", status_code=201)
def create(request: ConversationRequest):
    return _call(lambda: service.create_conversation(request.claim_id))


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: str):
    return _call(lambda: service.get_conversation(conversation_id))


@router.post("/conversations/{conversation_id}/messages")
def message(conversation_id: str, request: MessageRequest):
    """Invoke the local model/tool loop and persist actual success/failure evidence."""
    return _call(lambda: service.send_message(conversation_id, request.question))


@router.get("/conversations/{conversation_id}/turns/{turn_id}/cloud-trace")
def cloud_trace(conversation_id: str, turn_id: str):
    """Explicit read-only query of the project's Application Insights destination."""
    return _call(lambda: service.check_trace(conversation_id, turn_id))
