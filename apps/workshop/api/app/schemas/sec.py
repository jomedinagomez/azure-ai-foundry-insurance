"""Pydantic schemas for the SEC financial-table extraction feature."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

StatementType = Literal[
    "BalanceSheet",
    "IncomeStatement",
    "ComprehensiveIncome",
    "Equity",
    "CashFlow",
    "Other",
]


class SecSample(BaseModel):
    """A discoverable sample SEC filing under demo/sec/attachments/."""
    file_name: str
    file_type: Literal["pdf"]
    size_kb: float
    has_cached_result: bool
    has_ground_truth: bool


class SecLineItem(BaseModel):
    """One row in a financial statement table."""
    line_item: str
    level: int = 0
    is_section_header: bool = False
    is_subtotal: bool = False
    values: list[str] = Field(default_factory=list)
    value_confidences: Optional[list[Optional[float]]] = None
    confidence: Optional[float] = None


class SecStatement(BaseModel):
    """One financial statement table (a single sheet in the exported Excel)."""
    statement_type: StatementType
    table_title: str = ""
    company_name: str = ""
    unit: str = ""
    period_headers: list[str] = Field(default_factory=list)
    period_groups: list[str] = Field(default_factory=list)
    rows: list[SecLineItem] = Field(default_factory=list)
    # Source provenance (which classifier segment + page range produced this).
    source_category: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class SecExtractionMeta(BaseModel):
    source_file: str
    classifier_id: Optional[str] = None
    analyzer_id: Optional[str] = None
    elapsed_sec: Optional[float] = None
    retries: int = 0
    segment_categories: dict[str, int] = Field(
        default_factory=dict,
        description="Count of segments per category returned by the classifier.",
    )
    missing_statements: list[str] = Field(
        default_factory=list,
        description="Expected statement categories that were not detected.",
    )
    from_cache: bool = False
    run_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    pipeline_name: Optional[str] = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    cost: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class SecExtractionResult(BaseModel):
    file_name: str
    meta: SecExtractionMeta
    statements: list[SecStatement] = Field(default_factory=list)
    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Full CU payload (merged contents/fields) for the Raw JSON tab.",
    )


class SecExtractRequest(BaseModel):
    sample_name: str
    use_cache: bool = True
    save_as_canonical: bool = False


# ── Validation ──────────────────────────────────────────────────────────────
class SecValidationStatementSummary(BaseModel):
    statement_type: StatementType
    expected_rows: int
    actual_rows: int
    matched_rows: int
    missing_rows: list[str] = Field(default_factory=list)
    extra_rows: list[str] = Field(default_factory=list)


class SecValidationResult(BaseModel):
    file_name: str
    has_ground_truth: bool
    statements: list[SecValidationStatementSummary] = Field(default_factory=list)
    overall_match_rate: float = 0.0
