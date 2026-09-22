"""Pydantic contracts for the labeled property-claim analyzer demo."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class LabeledAnalyzerSample(BaseModel):
    file_name: str
    size_kb: float
    challenge: Literal["printed", "handwritten"]
    has_ground_truth: bool = True
    has_zero_shot_cache: bool = False
    has_labeled_cache: bool = False


class LabeledAnalyzerStatus(BaseModel):
    api_version: str
    model: str
    embedding_model: str
    training_files: list[str]
    holdout_files: list[str]
    labeled_data: dict[str, Any]
    cached_report: bool
    live_endpoint_configured: bool
    live_evaluation_enabled: bool
    storage_configured: bool
    analyzer_ids: dict[str, str]


class LabeledEvaluationRequest(BaseModel):
    sample_names: Optional[list[str]] = None
    repeats: int = Field(default=1, ge=1, le=3)
    force_live: bool = False


class LabelingProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    analyzer_id: str = Field(min_length=3, max_length=48)


class LabelFieldUpdate(BaseModel):
    value: Any = None
    source: Optional[str] = None
    spans: list[dict[str, int]] = Field(default_factory=list)


class DocumentLabelsUpdate(BaseModel):
    labels: dict[str, LabelFieldUpdate]
    reviewed: bool = False


class AutoLabelRequest(BaseModel):
    analyzer_id: Optional[str] = None