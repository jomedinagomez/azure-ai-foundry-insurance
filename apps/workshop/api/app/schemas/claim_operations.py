"""Read-only, explicitly synthetic claims lakehouse tool contract."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]
ActivityStatus = Literal["open", "awaiting_external", "completed"]
LineOfBusiness = Literal["commercial_property", "commercial_auto", "general_liability"]


class RecordModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PolicyRecord(RecordModel):
    policy_number: str
    effective_from: date
    effective_to: date
    currency: Literal["USD"]
    specimen_limit: Money
    specimen_deductible: Money
    source_ref: str


class PaymentRecord(RecordModel):
    payment_id: str
    kind: Literal["expense", "indemnity"]
    status: Literal["posted", "pending", "voided"]
    payee: str
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]
    purpose: str
    created_at: AwareDatetime
    updated_at: AwareDatetime
    posted_at: AwareDatetime | None

    @model_validator(mode="after")
    def validate_posting(self):
        if (self.status == "posted") != (self.posted_at is not None):
            raise ValueError("Only posted payments may have a posting timestamp.")
        if self.updated_at < self.created_at or (self.posted_at and not self.created_at <= self.posted_at <= self.updated_at):
            raise ValueError("Payment chronology is inconsistent.")
        return self


class FinancialRecord(RecordModel):
    currency: Literal["USD"]
    outstanding_indemnity_reserve: Money
    outstanding_expense_reserve: Money
    approved_settlement_amount: Money | None
    payments: list[PaymentRecord]


class ActivityRecord(RecordModel):
    activity_id: str
    title: str
    status: ActivityStatus
    owner_team: str
    priority: Literal["normal", "high"]
    blocking: bool
    requested_at: AwareDatetime
    due_date: date
    completed_at: AwareDatetime | None
    source_refs: list[str]

    @model_validator(mode="after")
    def validate_completion(self):
        if (self.status == "completed") != (self.completed_at is not None):
            raise ValueError("Only completed activities may have a completion timestamp.")
        if self.due_date < self.requested_at.date() or (self.completed_at and self.completed_at < self.requested_at):
            raise ValueError("Activity chronology is inconsistent.")
        return self


class LogNote(RecordModel):
    note_id: str
    recorded_at: AwareDatetime
    author_role: str
    category: Literal["document_review", "follow_up", "financial", "scope_review"]
    text: str
    activity_id: str | None
    source_refs: list[str]


class ClaimRecord(RecordModel):
    claim_id: Annotated[str, Field(pattern=r"^claim-[0-9]{3}$")]
    claim_number: Annotated[str, Field(pattern=r"^AV-26-[0-9]{6}$")]
    insured_name: str
    line_of_business: LineOfBusiness
    reported_loss: str
    loss_date: date
    status: Literal["open", "closed"]
    phase: str
    assigned_adjuster: str
    assigned_team: str
    opened_at: AwareDatetime
    updated_at: AwareDatetime
    coverage_decision: Literal["under_review", "accepted", "declined"]
    policy: PolicyRecord
    financials: FinancialRecord
    activities: list[ActivityRecord]
    log_notes: list[LogNote]

    @model_validator(mode="after")
    def validate_claim(self):
        if not self.policy.effective_from <= self.loss_date <= self.policy.effective_to:
            raise ValueError("The authored loss date must fall within the specimen policy period.")
        if self.opened_at.date() < self.loss_date or self.updated_at < self.opened_at:
            raise ValueError("Claim chronology is inconsistent.")
        for records, key in [(self.activities, "activity_id"), (self.log_notes, "note_id"),
                             (self.financials.payments, "payment_id")]:
            ids = [getattr(record, key) for record in records]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {key} in claim.")
        activity_ids = {activity.activity_id for activity in self.activities}
        if any(note.activity_id is not None and note.activity_id not in activity_ids for note in self.log_notes):
            raise ValueError("A log note references an unknown activity.")
        timestamps = [note.recorded_at for note in self.log_notes]
        timestamps += [activity.requested_at for activity in self.activities]
        timestamps += [activity.completed_at for activity in self.activities if activity.completed_at]
        timestamps += [payment.created_at for payment in self.financials.payments]
        timestamps += [payment.updated_at for payment in self.financials.payments]
        if any(not self.opened_at <= timestamp <= self.updated_at for timestamp in timestamps):
            raise ValueError("A record falls outside the claim's recorded time range.")
        if self.coverage_decision == "under_review" and self.financials.approved_settlement_amount is not None:
            raise ValueError("A claim under coverage review must not imply an approved settlement.")
        if self.status == "closed" and any(activity.blocking and activity.status != "completed" for activity in self.activities):
            raise ValueError("A closed claim cannot retain an open blocking activity.")
        return self


class ClaimsDataset(RecordModel):
    schema_version: Literal["1.0"]
    synthetic: Literal[True]
    source_system: Literal["simulated_databricks_genie"]
    as_of: AwareDatetime
    claims: Annotated[list[ClaimRecord], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_dataset(self):
        for field in ["claim_id", "claim_number", "policy"]:
            values = [claim.policy.policy_number if field == "policy" else getattr(claim, field) for claim in self.claims]
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {field} in dataset.")
        if any(claim.updated_at > self.as_of for claim in self.claims):
            raise ValueError("Claim updates cannot be newer than the dataset snapshot.")
        return self


class ToolMetadata(RecordModel):
    synthetic: Literal[True] = True
    source_system: Literal["simulated_databricks_genie"] = "simulated_databricks_genie"
    implementation: Literal["local_read_only_api"] = "local_read_only_api"
    schema_version: Literal["1.0"] = "1.0"
    as_of: AwareDatetime
    currency_values: str = "USD decimal strings; no binary floating-point arithmetic"
    caveat: str = "Synthetic operational snapshot, not a real Databricks/Genie response or a coverage decision."


class FinancialSnapshot(FinancialRecord):
    outstanding_reserve_total: Money
    paid_indemnity_total: Money
    paid_expense_total: Money
    paid_total: Money
    incurred_total: Money
    pending_payment_total: Money
    voided_request_total: Money
    definitions: dict[str, str]


class ActivitySnapshot(ActivityRecord):
    overdue_as_of_snapshot: bool
    currently_blocking: bool


class ClaimSnapshot(ClaimRecord):
    financials: FinancialSnapshot
    activities: list[ActivitySnapshot]


class ClaimSummary(RecordModel):
    claim_id: str
    claim_number: str
    insured_name: str
    line_of_business: LineOfBusiness
    status: Literal["open", "closed"]
    phase: str
    assigned_team: str
    assigned_adjuster: str
    blocking_activities: int
    overdue_activities: int
    outstanding_reserve_total: Money
    paid_total: Money
    currency: Literal["USD"] = "USD"


Data = TypeVar("Data")


class ToolResponse(RecordModel, Generic[Data]):
    metadata: ToolMetadata
    data: Data
