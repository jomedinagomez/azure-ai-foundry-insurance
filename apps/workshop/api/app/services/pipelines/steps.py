"""Step handlers. Each handler is `(input_path, params, ctx) -> StepResult`.

The runner threads `output_path` between steps. The terminal `cu_analyze`
step also returns `payload` (the CU response), which the runner promotes
to the run result.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from .schema import StepResult


# ── Reach the demo/sov/preprocess library so we share one impl ────────────
def _ensure_preprocess_importable():
    # Resolve repo root: api/app/services/pipelines/steps.py -> 6 parents up
    here = Path(__file__).resolve()
    repo_root = here.parents[6] if len(here.parents) > 6 else here.parents[-1]
    demo_root = Path(os.environ.get("SOV_DEMO_ROOT") or (repo_root / "demo" / "sov"))
    p = str(demo_root)
    if p not in sys.path:
        sys.path.insert(0, p)


_ensure_preprocess_importable()


# ── Run context (per-pipeline scratch dir, output sink, etc.) ─────────────
class StepContext:
    def __init__(self, work_dir: Path, on_log: Callable[[str], None] | None = None):
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.on_log = on_log or (lambda _msg: None)


# ── Handlers ──────────────────────────────────────────────────────────────
def step_xlsx_preflight(input_path: Path, params: dict[str, Any], ctx: StepContext) -> StepResult:
    from preprocess import apply_print_preflight  # type: ignore

    autofit = bool(params.get("autofit", True))
    print_gridlines = bool(params.get("print_gridlines", False))
    out = ctx.work_dir / f"{input_path.stem}.print-ready.xlsx"
    out_path = apply_print_preflight(
        input_path, out, autofit=autofit, print_gridlines=print_gridlines
    )
    return StepResult(
        output_path=str(out_path),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        meta={
            "size_bytes": out_path.stat().st_size,
            "autofit": autofit,
            "print_gridlines": print_gridlines,
        },
    )


def step_libreoffice_to_pdf(input_path: Path, params: dict[str, Any], ctx: StepContext) -> StepResult:
    from preprocess import convert_libreoffice  # type: ignore

    out_path = convert_libreoffice(input_path, ctx.work_dir)
    return StepResult(
        output_path=str(out_path),
        content_type="application/pdf",
        meta={"size_bytes": out_path.stat().st_size},
    )


def step_pdf_to_tiff(input_path: Path, params: dict[str, Any], ctx: StepContext) -> StepResult:
    from preprocess import rasterize_pdf_to_tiff  # type: ignore

    dpi = int(params.get("dpi", 800))
    out_path = rasterize_pdf_to_tiff(input_path, ctx.work_dir, dpi=dpi)
    return StepResult(
        output_path=str(out_path),
        content_type="image/tiff",
        meta={"size_bytes": out_path.stat().st_size, "dpi": dpi},
    )


def step_extract_embedded_images(input_path: Path, params: dict[str, Any], ctx: StepContext) -> StepResult:
    """Pull every `xl/media/*` image out of an xlsx. Stored alongside the
    xlsx in the work dir; the next step (`cu_analyze`) sees them via
    `pattern_c_images` in its meta. Used by Pattern C."""
    from app.services.sov_service import _extract_embedded_images  # type: ignore

    image_dir = ctx.work_dir / f"{input_path.stem}__images"
    images = _extract_embedded_images(input_path, image_dir)
    return StepResult(
        # Pass the original xlsx forward; analyze handles the fan-out itself
        output_path=str(input_path),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        meta={
            "image_count": len(images),
            "image_paths": [str(p) for p in images],
        },
    )


def step_cu_analyze(input_path: Path, params: dict[str, Any], ctx: StepContext) -> StepResult:
    """Run the configured analyzer against `input_path`. Honors three modes:

    - `mode: "single"` (default): one analyze call.
    - `mode: "fan_out_xlsx_images"`: workbook + each embedded image, merged
      client-side. Equivalent to Pattern C; expects a preceding
      `extract_embedded_images` step to have populated `prev_meta.image_paths`
      (passed in via `params['_image_paths']` by the runner).

    Required params:
      - `analyzer_id`: which analyzer to invoke.
      - `template_file`: which template to register if the analyzer is missing.
      - `content_type` (optional): override the suffix-based content type.
    """
    from app.services.sov_service import (  # type: ignore
        _analyze_one,
        _ensure_analyzer,
        _merge_image_locations,
        CONTENT_TYPE_BY_SUFFIX,
    )

    analyzer_id = params["analyzer_id"]
    template_file = params["template_file"]
    mode = params.get("mode", "single")

    _ensure_analyzer(analyzer_id, template_file)

    suffix = input_path.suffix.lower()
    content_type = (
        params.get("content_type")
        or CONTENT_TYPE_BY_SUFFIX.get(suffix)
    )
    if not content_type:
        raise ValueError(f"No content type for {input_path.name}")

    t0 = time.perf_counter()
    payload, t_main = _analyze_one(
        input_path, analyzer_id, template_file, content_type
    )

    # Optional: image fan-out + merge (Pattern C-equivalent)
    image_paths_raw = params.get("_image_paths") or []
    image_paths = [Path(p) for p in image_paths_raw]
    img_payloads: list[dict] = []
    t_imgs = 0.0
    if mode == "fan_out_xlsx_images" and image_paths:
        for img in image_paths:
            ip, ie = _analyze_one(
                img,
                analyzer_id,
                template_file,
                CONTENT_TYPE_BY_SUFFIX.get(img.suffix.lower(), "application/octet-stream"),
            )
            img_payloads.append(ip)
            t_imgs += ie

    # Merge image-only Locations[] into the main payload (sov_service helper)
    if img_payloads:
        try:
            content0 = (payload.get("contents") or [{}])[0]
            fields = content0.setdefault("fields", {})
            locs_field = fields.setdefault("Locations", {"type": "array", "valueArray": []})
            base_locs = locs_field.get("valueArray") or []
            image_batches: list[list[dict]] = []
            for ip in img_payloads:
                ic = (ip.get("contents") or [{}])[0]
                ifields = ic.get("fields", {}) or {}
                iloc = ifields.get("Locations", {}) or {}
                image_batches.append(iloc.get("valueArray") or [])
            merged, added, complements = _merge_image_locations(base_locs, image_batches)
            locs_field["valueArray"] = merged
        except Exception as e:
            # If the merge helper signature has shifted, leave the base payload alone
            print(f"[pipeline] merge skipped: {e}")
            added = complements = 0

    payload.setdefault("_meta", {})
    payload["_meta"].update({
        "analyzer_id": analyzer_id,
        "template_file": template_file,
        "elapsed_sec": round(time.perf_counter() - t0, 2),
        "main_call_sec": round(t_main, 2),
        "image_call_sec": round(t_imgs, 2) if t_imgs else 0.0,
        "image_call_count": len(img_payloads),
    })

    return StepResult(
        output_path=str(input_path),
        content_type=content_type,
        meta={
            "analyzer_id": analyzer_id,
            "template_file": template_file,
            "image_call_count": len(img_payloads),
        },
        payload=payload,
    )


# ── Registry ──────────────────────────────────────────────────────────────
HANDLERS: dict[str, Callable[[Path, dict[str, Any], StepContext], StepResult]] = {
    "xlsx_preflight": step_xlsx_preflight,
    "libreoffice_to_pdf": step_libreoffice_to_pdf,
    "pdf_to_tiff": step_pdf_to_tiff,
    "extract_embedded_images": step_extract_embedded_images,
    "cu_analyze": step_cu_analyze,
}
