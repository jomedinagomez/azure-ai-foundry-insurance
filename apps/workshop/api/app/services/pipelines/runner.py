"""Run a pipeline. Two flavors:

- `run_pipeline()` returns the final CU payload (sync).
- `run_pipeline_stream()` yields `StepEvent`s for SSE consumers.
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Iterator

from .library import load_pipeline
from .schema import Pipeline, PipelineRunResult, StepEvent
from .steps import HANDLERS, StepContext


def _resolve(pipeline_or_id: Pipeline | str) -> Pipeline:
    if isinstance(pipeline_or_id, Pipeline):
        return pipeline_or_id
    p = load_pipeline(pipeline_or_id)
    if p is None:
        raise ValueError(f"Pipeline not found: {pipeline_or_id}")
    return p


def _validate_terminal_step(pipeline: Pipeline) -> None:
    if not pipeline.steps:
        raise ValueError(f"Pipeline {pipeline.id!r} has no steps")
    if pipeline.steps[-1].kind != "cu_analyze":
        raise ValueError(
            f"Pipeline {pipeline.id!r} must end with a `cu_analyze` step "
            f"(found {pipeline.steps[-1].kind})"
        )


def run_pipeline(
    pipeline_or_id: Pipeline | str,
    input_path: str | Path,
    *,
    work_dir: Path | None = None,
) -> PipelineRunResult:
    """Synchronous run. Returns the CU payload + per-step timings + artifacts."""
    pipeline = _resolve(pipeline_or_id)
    _validate_terminal_step(pipeline)

    cleanup_tmp: tempfile.TemporaryDirectory | None = None
    if work_dir is None:
        cleanup_tmp = tempfile.TemporaryDirectory(prefix=f"pipeline_{pipeline.id}_")
        work_dir = Path(cleanup_tmp.name)
    ctx = StepContext(work_dir=work_dir)

    timings: dict[str, float] = {}
    artifacts: dict[str, str] = {"input": str(input_path)}
    current_path = Path(input_path)
    last_meta: dict = {}
    payload: dict | None = None

    try:
        for i, step in enumerate(pipeline.steps):
            handler = HANDLERS.get(step.kind)
            if handler is None:
                raise ValueError(f"Unknown step kind: {step.kind}")
            params = dict(step.params)
            # Image fan-out plumbing: if a previous step extracted images, expose
            # them to the cu_analyze handler under a private key.
            if step.kind == "cu_analyze" and "image_paths" in last_meta:
                params["_image_paths"] = last_meta.get("image_paths")

            t0 = time.perf_counter()
            result = handler(current_path, params, ctx)
            timings[step.id] = round(time.perf_counter() - t0, 2)
            artifacts[step.id] = result.output_path or str(current_path)
            last_meta = result.meta or {}
            if result.payload is not None:
                payload = result.payload
            if result.output_path:
                current_path = Path(result.output_path)

        if payload is None:
            raise RuntimeError(
                f"Pipeline {pipeline.id!r} produced no payload (terminal step did not set one)"
            )
        # Stamp pipeline meta on the payload so downstream code can introspect.
        payload.setdefault("_meta", {})
        payload["_meta"].update({
            "pipeline_id": pipeline.id,
            "pipeline_name": pipeline.name,
            "pipeline_timings": timings,
            "pipeline_artifacts": artifacts,
        })
        return PipelineRunResult(payload=payload, timings=timings, artifacts=artifacts)
    finally:
        # Note: we leave the work_dir on disk if the caller provided one.
        # The temp dir we created is cleaned up automatically by Python.
        if cleanup_tmp is not None:
            try:
                cleanup_tmp.cleanup()
            except Exception:
                pass


def run_pipeline_stream(
    pipeline_or_id: Pipeline | str,
    input_path: str | Path,
    *,
    work_dir: Path | None = None,
) -> Iterator[StepEvent | PipelineRunResult]:
    """Generator: emits a `StepEvent` for each step's lifecycle and finally
    yields a `PipelineRunResult`. Suitable for Server-Sent Events."""
    pipeline = _resolve(pipeline_or_id)
    _validate_terminal_step(pipeline)

    cleanup_tmp: tempfile.TemporaryDirectory | None = None
    if work_dir is None:
        cleanup_tmp = tempfile.TemporaryDirectory(prefix=f"pipeline_{pipeline.id}_")
        work_dir = Path(cleanup_tmp.name)
    ctx = StepContext(work_dir=work_dir)

    timings: dict[str, float] = {}
    artifacts: dict[str, str] = {"input": str(input_path)}
    current_path = Path(input_path)
    last_meta: dict = {}
    payload: dict | None = None

    try:
        # Emit pending events for visibility
        for i, step in enumerate(pipeline.steps):
            yield StepEvent(
                pipeline_id=pipeline.id,
                step_index=i,
                step_id=step.id,
                step_kind=step.kind,
                status="pending",
            )

        for i, step in enumerate(pipeline.steps):
            yield StepEvent(
                pipeline_id=pipeline.id,
                step_index=i,
                step_id=step.id,
                step_kind=step.kind,
                status="running",
            )

            handler = HANDLERS.get(step.kind)
            if handler is None:
                yield StepEvent(
                    pipeline_id=pipeline.id,
                    step_index=i,
                    step_id=step.id,
                    step_kind=step.kind,
                    status="error",
                    error=f"Unknown step kind: {step.kind}",
                )
                return

            params = dict(step.params)
            if step.kind == "cu_analyze" and "image_paths" in last_meta:
                params["_image_paths"] = last_meta.get("image_paths")

            t0 = time.perf_counter()
            try:
                result = handler(current_path, params, ctx)
            except Exception as e:
                yield StepEvent(
                    pipeline_id=pipeline.id,
                    step_index=i,
                    step_id=step.id,
                    step_kind=step.kind,
                    status="error",
                    elapsed_sec=round(time.perf_counter() - t0, 2),
                    error=str(e)[:500],
                )
                return

            elapsed = round(time.perf_counter() - t0, 2)
            timings[step.id] = elapsed
            artifacts[step.id] = result.output_path or str(current_path)
            last_meta = result.meta or {}
            if result.payload is not None:
                payload = result.payload
            if result.output_path:
                current_path = Path(result.output_path)

            yield StepEvent(
                pipeline_id=pipeline.id,
                step_index=i,
                step_id=step.id,
                step_kind=step.kind,
                status="done",
                elapsed_sec=elapsed,
                meta=last_meta,
            )

        if payload is None:
            return
        payload.setdefault("_meta", {})
        payload["_meta"].update({
            "pipeline_id": pipeline.id,
            "pipeline_name": pipeline.name,
            "pipeline_timings": timings,
            "pipeline_artifacts": artifacts,
        })
        yield PipelineRunResult(payload=payload, timings=timings, artifacts=artifacts)
    finally:
        if cleanup_tmp is not None:
            try:
                cleanup_tmp.cleanup()
            except Exception:
                pass
