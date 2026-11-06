"""Authored operational records, separate from indexed document evidence."""
from decimal import Decimal
from pathlib import Path, PurePosixPath

from app.schemas.claim_operations import (
    ActivitySnapshot, ClaimsDataset, ClaimRecord, ClaimSnapshot, ClaimSummary,
    FinancialSnapshot, ToolMetadata, ToolResponse,
)

ROOT = Path(__file__).resolve().parents[5]
DATA_PATH = ROOT / "data" / "claims-operations" / "claims.json"
EVIDENCE_ROOT = ROOT / "data" / "claims"
ZERO = Decimal("0.00")
DEFINITIONS = {
    "outstanding_reserve_total": "Outstanding indemnity reserve + outstanding expense reserve; not a contractor estimate or approved settlement.",
    "paid_total": "Posted indemnity + posted expense payments only. Pending and voided requests are excluded.",
    "incurred_total": "Outstanding reserve total + posted paid total, before any recovery. It is not a settlement calculation.",
    "pending_payment_total": "Pending requests only; not money already paid.",
    "voided_request_total": "Voided-before-posting requests only; neither paid amounts nor a deduction from paid totals.",
    "approved_settlement_amount": "Null means no approved settlement amount is recorded; null is not zero.",
    "specimen_policy": "Limits and deductibles are specimen schedule values, not an automatic coverage or net-payment decision.",
}


def load_dataset() -> ClaimsDataset:
    dataset = ClaimsDataset.model_validate_json(DATA_PATH.read_text(encoding="utf-8"))
    for claim in dataset.claims:
        refs = [claim.policy.source_ref]
        refs += [ref for activity in claim.activities for ref in activity.source_refs]
        refs += [ref for note in claim.log_notes for ref in note.source_refs]
        for ref in refs:
            relative = PurePosixPath(ref)
            path = EVIDENCE_ROOT.joinpath(*relative.parts).resolve()
            if not relative.parts or relative.parts[0] != claim.claim_id or not path.is_relative_to((EVIDENCE_ROOT / claim.claim_id).resolve()) or not path.is_file():
                raise ValueError(f"Invalid evidence reference for {claim.claim_id}: {ref}")
    return dataset


def resolve_claim(dataset: ClaimsDataset, reference: str) -> ClaimRecord:
    reference = reference.strip().casefold()
    claim = next((claim for claim in dataset.claims
                  if reference in {claim.claim_id.casefold(), claim.claim_number.casefold()}), None)
    if claim is None:
        raise LookupError("No structured record exists for that claim reference.")
    return claim


def financial_snapshot(claim: ClaimRecord) -> FinancialSnapshot:
    record = claim.financials
    paid_indemnity = sum((payment.amount for payment in record.payments
                          if payment.status == "posted" and payment.kind == "indemnity"), ZERO)
    paid_expense = sum((payment.amount for payment in record.payments
                       if payment.status == "posted" and payment.kind == "expense"), ZERO)
    reserve = record.outstanding_indemnity_reserve + record.outstanding_expense_reserve
    return FinancialSnapshot(
        **record.model_dump(),
        outstanding_reserve_total=reserve,
        paid_indemnity_total=paid_indemnity, paid_expense_total=paid_expense,
        paid_total=paid_indemnity + paid_expense,
        incurred_total=reserve + paid_indemnity + paid_expense,
        pending_payment_total=sum((payment.amount for payment in record.payments if payment.status == "pending"), ZERO),
        voided_request_total=sum((payment.amount for payment in record.payments if payment.status == "voided"), ZERO),
        definitions=DEFINITIONS,
    )


def snapshot(dataset: ClaimsDataset, claim: ClaimRecord) -> ClaimSnapshot:
    activities = [ActivitySnapshot(
        **activity.model_dump(),
        overdue_as_of_snapshot=activity.status != "completed" and activity.due_date < dataset.as_of.date(),
        currently_blocking=activity.blocking and activity.status != "completed",
    ) for activity in sorted(claim.activities, key=lambda activity: (activity.status == "completed", activity.due_date, activity.activity_id))]
    return ClaimSnapshot(
        **claim.model_dump(exclude={"financials", "activities", "log_notes"}),
        financials=financial_snapshot(claim), activities=activities,
        log_notes=sorted(claim.log_notes, key=lambda note: note.recorded_at),
    )


def get_snapshot(reference: str) -> ToolResponse[ClaimSnapshot]:
    dataset = load_dataset()
    return ToolResponse(metadata=ToolMetadata(as_of=dataset.as_of),
                        data=snapshot(dataset, resolve_claim(dataset, reference)))


def list_claims(status: str | None = None, line_of_business: str | None = None) -> ToolResponse[list[ClaimSummary]]:
    dataset = load_dataset()
    summaries = []
    for claim in dataset.claims:
        if (status and claim.status != status) or (line_of_business and claim.line_of_business != line_of_business):
            continue
        data = snapshot(dataset, claim)
        summaries.append(ClaimSummary(
            claim_id=data.claim_id, claim_number=data.claim_number, insured_name=data.insured_name,
            line_of_business=data.line_of_business, status=data.status, phase=data.phase,
            assigned_team=data.assigned_team, assigned_adjuster=data.assigned_adjuster,
            blocking_activities=sum(activity.currently_blocking for activity in data.activities),
            overdue_activities=sum(activity.overdue_as_of_snapshot for activity in data.activities),
            outstanding_reserve_total=data.financials.outstanding_reserve_total, paid_total=data.financials.paid_total,
        ))
    return ToolResponse(metadata=ToolMetadata(as_of=dataset.as_of), data=summaries)
