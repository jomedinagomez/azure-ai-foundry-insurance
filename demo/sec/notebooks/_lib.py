"""Notebook helper — adds `apps/workshop/api` to sys.path so notebooks can
import the same service module the API uses.

Convention: every SEC notebook starts with
    from _lib import sec_service, sec_excel

so there is one implementation of classify/extract/merge/export logic
shared between the API, the UI, and the workshop notebooks.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
# demo/sec/notebooks/_lib.py -> repo root is 3 parents up
REPO_ROOT = _HERE.parents[3]
API_ROOT = REPO_ROOT / "apps" / "workshop" / "api"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# Auto-load the repo-root .env when present so APP_CONTENT_UNDERSTANDING_ENDPOINT
# is picked up without each notebook re-doing it.
try:
    from dotenv import load_dotenv  # type: ignore

    _root_env = REPO_ROOT / ".env"
    if _root_env.exists():
        load_dotenv(_root_env)
except Exception:
    pass

from app.services import sec_excel, sec_service  # noqa: E402

DEMO_ROOT = sec_service.SEC_DEMO_ROOT
SAMPLE_DIR = sec_service.ATTACH_DIR
CACHE_DIR = sec_service.CU_OUTPUT_DIR
EXPECTED_DIR = sec_service.EXPECTED_DIR
TEMPLATE_DIR = sec_service.TEMPLATE_DIR

__all__ = [
    "sec_service",
    "sec_excel",
    "DEMO_ROOT",
    "SAMPLE_DIR",
    "CACHE_DIR",
    "EXPECTED_DIR",
    "TEMPLATE_DIR",
    "REPO_ROOT",
    "API_ROOT",
]
