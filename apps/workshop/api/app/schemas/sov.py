from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SovSample(BaseModel):
    """A discoverable sample SOV file under demo/sov/attachments/."""
    file_name: str
    file_type: Literal["xlsx", "pdf"]
    size_kb: float
    has_cached_result: bool
    has_ground_truth: bool


class SovExtractionMeta(BaseModel):
    """`_meta` block from extraction (mirrors notebook output shape)."""
    source_file: str
    # `approach` is optional now that pipelines have replaced patterns. The
    # SOV tab still surfaces a `pattern` letter for the legacy badge UI.
    approach: Optional[str] = None
    analyzer_id: Optional[str] = None
    pattern: Literal["A", "B", "C"] = "A"
    elapsed_sec: Optional[float] = None
    image_calls: Optional[int] = None
    added_from_images: Optional[int] = None
    field_complements: Optional[int] = None
    elapsed_main_sec: Optional[float] = None
    elapsed_images_sec: Optional[float] = None
    elapsed_total_sec: Optional[float] = None
    from_cache: bool = False
    # Pipeline metadata (None when the payload came from the legacy path).
    pipeline_id: Optional[str] = None
    pipeline_name: Optional[str] = None

    model_config = {"extra": "allow"}


class SovAccountSummary(BaseModel):
    """Headline account-level fields, unwrapped from CU value-objects."""
    insured_name: Optional[str] = None
    dba: Optional[str] = None
    mailing_address: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    primary_operations: Optional[str] = None
    naics: Optional[str] = None
    currency: Optional[str] = None
    valuation_date: Optional[str] = None
    total_insured_value: Optional[float] = None
    location_count: Optional[float] = None
    broker_name: Optional[str] = None
    broker_contact: Optional[str] = None
    broker_email: Optional[str] = None
    broker_phone: Optional[str] = None
    prepared_by: Optional[str] = None
    prepared_date: Optional[str] = None


class SovLocation(BaseModel):
    """A single normalized location row."""
    location_number: Optional[Any] = None
    building_number: Optional[Any] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    construction_type: Optional[str] = None
    occupancy: Optional[str] = None
    operations_description: Optional[str] = None
    year_built: Optional[Any] = None
    stories: Optional[Any] = None
    square_footage: Optional[Any] = None
    unit_count: Optional[Any] = None
    building_value: Optional[Any] = None
    bpp_value: Optional[Any] = None
    bi_ee_value: Optional[Any] = None
    sprinklered: Optional[Any] = None
    protection_class: Optional[Any] = None
    roof_year: Optional[Any] = None
    flood_zone: Optional[str] = None
    distance_to_coast_mi: Optional[Any] = None
    notes: Optional[str] = None
    source: Optional[str] = Field(default=None, description="xlsx | image[i] | xlsx+image[i]")


class SovExtractionResult(BaseModel):
    file_name: str
    meta: SovExtractionMeta
    account: SovAccountSummary
    account_confidence: dict[str, Optional[float]] = Field(default_factory=dict)
    locations: list[SovLocation]
    locations_confidence: list[dict[str, Optional[float]]] = Field(default_factory=list)
    location_count_actual: int
    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Full CU payload (contents/fields/_meta) for the Raw JSON tab.",
    )


# ── Validation ──────────────────────────────────────────────────────────────
class SovValidationDiff(BaseModel):
    scope: Literal["account", "location"]
    location_key: Optional[Any] = None
    field: str
    actual: Optional[Any] = None
    expected: Optional[Any] = None
    in_source: bool
    match: bool


class SovValidationSummary(BaseModel):
    file_name: str
    location_count_actual: int
    location_count_expected: int
    account_mismatches_in_source: int
    location_mismatches_in_source: int


class SovValidationResult(BaseModel):
    summary: SovValidationSummary
    account: list[SovValidationDiff]
    locations: list[SovValidationDiff]
    has_ground_truth: bool = True


class SovExtractRequest(BaseModel):
    sample_name: str
    force_refresh: bool = False
    pattern: Optional[Literal["A", "B", "C"]] = None
