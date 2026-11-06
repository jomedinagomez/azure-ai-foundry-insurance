"""Local read-only tool standing in for structured Databricks/Genie access."""
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from app.schemas.claim_operations import (
    ActivitySnapshot, ClaimSnapshot, ClaimSummary, FinancialSnapshot,
    LineOfBusiness, LogNote, ToolResponse,
)
from app.services import claim_operations_service as service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/claims-operations", tags=["claims-operations"])


def _snapshot(reference: str) -> ToolResponse[ClaimSnapshot]:
    try:
        return service.get_snapshot(reference)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError, ValidationError) as exc:
        logger.exception("Structured claims dataset is unavailable or invalid")
        raise HTTPException(500, "The synthetic claims dataset is unavailable or invalid; inspect the API log.") from exc


@router.get("/claims", response_model=ToolResponse[list[ClaimSummary]], operation_id="list_structured_claims")
def list_claims(
    status: Literal["open", "closed"] | None = None,
    line_of_business: LineOfBusiness | None = None,
):
    """List synthetic system-of-record summaries; this does not query document Search."""
    try:
        return service.list_claims(status, line_of_business)
    except (OSError, ValueError, ValidationError) as exc:
        logger.exception("Structured claims dataset is unavailable or invalid")
        raise HTTPException(500, "The synthetic claims dataset is unavailable or invalid; inspect the API log.") from exc


@router.get("/claims/{claim_reference}", response_model=ToolResponse[ClaimSnapshot],
            operation_id="get_structured_claim_snapshot")
def get_claim_snapshot(claim_reference: str):
    """Read assignment, policy, exact financials, activities and notes by folder ID or claim number."""
    return _snapshot(claim_reference)


@router.get("/claims/{claim_reference}/financials", response_model=ToolResponse[FinancialSnapshot],
            operation_id="get_structured_claim_financials")
def get_claim_financials(claim_reference: str):
    """Read the ledger and exact totals. Pending/voided requests are never counted as paid."""
    result = _snapshot(claim_reference)
    return ToolResponse(metadata=result.metadata, data=result.data.financials)


@router.get("/claims/{claim_reference}/activities", response_model=ToolResponse[list[ActivitySnapshot]],
            operation_id="get_structured_claim_activities")
def get_claim_activities(
    claim_reference: str,
    status: Literal["open", "awaiting_external", "completed"] | None = None,
    blocking_only: bool = False,
):
    """Read actionable work. Overdue is evaluated against the fixed dataset snapshot, not today's clock."""
    result = _snapshot(claim_reference)
    activities = [activity for activity in result.data.activities
                  if (not status or activity.status == status) and (not blocking_only or activity.currently_blocking)]
    return ToolResponse(metadata=result.metadata, data=activities)


@router.get("/claims/{claim_reference}/log-notes", response_model=ToolResponse[list[LogNote]],
            operation_id="get_structured_claim_log_notes")
def get_claim_log_notes(claim_reference: str, limit: int = Query(20, ge=1, le=50)):
    """Read most-recent notes, retaining stable IDs, author roles and recorded timestamps."""
    result = _snapshot(claim_reference)
    return ToolResponse(metadata=result.metadata, data=list(reversed(result.data.log_notes))[:limit])
