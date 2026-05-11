"""Pydantic models for pipelines."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

StepKind = Literal[
    "xlsx_preflight",
    "libreoffice_to_pdf",
    "pdf_to_tiff",
    "extract_embedded_images",
    "cu_analyze",
]


class PipelineStep(BaseModel):
    """One step in a pipeline. `kind` selects the registered handler in
    `steps.py`; `params` is opaque to the pipeline machinery and passed to
    the handler verbatim."""
    id: str
    kind: StepKind
    label: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class Pipeline(BaseModel):
    """A pipeline routes one or more file extensions through an ordered list
    of steps. The last step must be `cu_analyze`."""
    id: str
    name: str
    description: str = ""
    input_extensions: list[str] = Field(
        ...,
        description="Which file suffixes (lowercase, dot-prefixed) this pipeline accepts.",
    )
    is_default: bool = False
    steps: list[PipelineStep]


class StepResult(BaseModel):
    """Returned by every step. `output_path` becomes the next step's input.
    `payload` is set only by terminal `cu_analyze`."""
    output_path: str | None = None
    content_type: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    payload: Optional[dict[str, Any]] = None


class StepEvent(BaseModel):
    """Streaming event for the SSE runner."""
    pipeline_id: str
    step_index: int
    step_id: str
    step_kind: StepKind
    status: Literal["pending", "running", "done", "error"]
    elapsed_sec: float | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class PipelineRunResult(BaseModel):
    """Sync run result. Mirrors what `analyze_sample` returns today."""
    payload: dict[str, Any]
    timings: dict[str, float]
    artifacts: dict[str, str]
