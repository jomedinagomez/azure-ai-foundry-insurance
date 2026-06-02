"""Pro Mode schemas (Content Understanding pro mode demo).

See demo/pro/README.md for context. The API surface mirrors the SOV/SEC
routers in shape but is intentionally simpler — pro mode does not return
confidence scores or grounding, so we surface the raw CU reasoning fields
plus a small rule-engine layer for fraud signals.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high"]
Scenario = Literal["claims", "fraud"]


class ProSampleFile(BaseModel):
    name: str
    kind: str
    media_type: str
    tampered: bool = False


class ProSampleManifest(BaseModel):
    """`manifest.json` shape for a bundled sample claim package."""

    id: str
    title: str
    scenario: Scenario
    loss_type: str
    description: str
    claimant: Optional[str] = None
    policy_number: Optional[str] = None
    vin: Optional[str] = None
    vehicle: Optional[str] = None
    files: list[ProSampleFile] = Field(default_factory=list)
    expected_signals: list[dict[str, Any]] = Field(default_factory=list)
    expected_risk_score_range: Optional[tuple[int, int]] = None
    source: Optional[dict[str, Any]] = None


class FraudSignal(BaseModel):
    """One detected fraud signal (rule engine output)."""

    rule_id: str
    severity: Severity
    title: str
    evidence: str
    source_documents: list[str] = Field(default_factory=list)
    weight: int = Field(..., description="Contribution to the blended risk score, 0..100")


class ProClaimsFields(BaseModel):
    """Parsed structured fields from the pro_claims analyzer."""

    claimant_name: Optional[str] = None
    policy_number: Optional[str] = None
    vin: Optional[str] = None
    date_of_loss: Optional[str] = None
    loss_location: Optional[str] = None
    incident_narrative: Optional[str] = None
    estimated_total: Optional[float] = None
    damage_visible_in_photo: Optional[str] = None
    coverage_applies: Optional[str] = None
    police_report_present: Optional[str] = None
    document_set_completeness: Optional[str] = None
    claims_handler_verdict: Optional[str] = None


class ProFraudFields(BaseModel):
    """Parsed structured fields from the pro_fraud analyzer."""

    vin_consistency: Optional[str] = None
    vin_consistency_evidence: Optional[str] = None
    policy_number_consistency: Optional[str] = None
    claimant_name_consistency: Optional[str] = None
    totals_vs_sub_limit: Optional[str] = None
    totals_evidence: Optional[str] = None
    estimate_date_vs_date_of_loss: Optional[str] = None
    date_evidence: Optional[str] = None
    narrative_image_consistency: Optional[str] = None
    narrative_image_evidence: Optional[str] = None
    overall_fraud_indication: Optional[str] = None
    rationale: Optional[str] = None


class ProMeta(BaseModel):
    sample_id: Optional[str] = None
    scenario: Scenario
    analyzer_id: str
    api_version: str
    elapsed_sec: Optional[float] = None
    input_files: list[str] = Field(default_factory=list)


class ProClaimsResult(BaseModel):
    meta: ProMeta
    fields: ProClaimsFields
    raw: dict[str, Any] = Field(default_factory=dict)


class ProFraudResult(BaseModel):
    meta: ProMeta
    fields: ProFraudFields
    cu_signals: list[FraudSignal] = Field(
        default_factory=list,
        description="Signals derived from the pro_fraud analyzer's classify findings.",
    )
    rule_signals: list[FraudSignal] = Field(
        default_factory=list,
        description="Signals derived from the local rule engine over pro_claims fields.",
    )
    risk_score: int = Field(0, ge=0, le=100, description="Blended risk score, 0..100")
    risk_band: Literal["low", "medium", "high"]
    raw: dict[str, Any] = Field(default_factory=dict)


class ProHealthcheck(BaseModel):
    endpoint_configured: bool
    api_version: str
    analyzers: dict[str, bool] = Field(
        default_factory=dict,
        description="Map of analyzer_id -> whether it is already deployed in the CU resource.",
    )
    samples_available: list[str] = Field(default_factory=list)
    pro_mode_supported: Optional[bool] = None
    error: Optional[str] = None
