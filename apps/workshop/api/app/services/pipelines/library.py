"""Pipeline storage: JSON files under `library/`."""
from __future__ import annotations

import json
from pathlib import Path

from .schema import Pipeline

LIBRARY_DIR = Path(__file__).resolve().parent / "library"


def _ensure_dir() -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def load_pipelines() -> list[Pipeline]:
    """Read every `*.json` in the library, sorted by id."""
    _ensure_dir()
    out: list[Pipeline] = []
    for p in sorted(LIBRARY_DIR.glob("*.json")):
        out.append(Pipeline.model_validate_json(p.read_text(encoding="utf-8")))
    return out


def load_pipeline(pipeline_id: str) -> Pipeline | None:
    p = LIBRARY_DIR / f"{pipeline_id}.json"
    if not p.exists():
        return None
    return Pipeline.model_validate_json(p.read_text(encoding="utf-8"))


def save_pipeline(pipeline: Pipeline) -> None:
    _ensure_dir()
    p = LIBRARY_DIR / f"{pipeline.id}.json"
    p.write_text(
        json.dumps(pipeline.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def delete_pipeline(pipeline_id: str) -> bool:
    p = LIBRARY_DIR / f"{pipeline_id}.json"
    if p.exists():
        p.unlink()
        return True
    return False


def default_pipeline_for(extension: str) -> Pipeline | None:
    """Return the pipeline tagged `is_default: true` for the given suffix
    (lowercase, dot-prefixed). Falls back to the first pipeline that
    accepts the extension. Returns None if no pipeline matches."""
    extension = extension.lower()
    matches: list[Pipeline] = []
    for p in load_pipelines():
        exts = [e.lower() for e in p.input_extensions]
        if extension in exts:
            matches.append(p)
    if not matches:
        return None
    for p in matches:
        if p.is_default:
            return p
    return matches[0]
