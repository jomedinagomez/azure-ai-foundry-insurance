"""Pipelines: ordered, JSON-defined preprocessing + analyze chains.

A pipeline runs N steps over a single input file, threading the previous
step's output forward. The terminal step is always `cu_analyze` and produces
the same payload shape that `sov_service.analyze_sample` returns today, so
downstream code (validator, projector, UI) stays unchanged.

Public entry points:
- `runner.run_pipeline(pipeline_id, input_path)` -> CU payload (sync).
- `runner.run_pipeline_stream(pipeline_id, input_path)` -> generator yielding
  per-step status events for SSE.
- `library.load_pipelines()` / `library.load_pipeline(id)` -> read seeded
  pipeline JSON from `library/`.
"""
from .schema import Pipeline, PipelineRunResult, PipelineStep, StepEvent, StepResult
from .library import load_pipelines, load_pipeline, default_pipeline_for
from .runner import run_pipeline, run_pipeline_stream

__all__ = [
    "Pipeline",
    "PipelineRunResult",
    "PipelineStep",
    "StepEvent",
    "StepResult",
    "load_pipelines",
    "load_pipeline",
    "default_pipeline_for",
    "run_pipeline",
    "run_pipeline_stream",
]
