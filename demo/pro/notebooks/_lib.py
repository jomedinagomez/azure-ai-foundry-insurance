"""Notebook helper for the Pro Mode demo. Adds `apps/workshop/api` to
sys.path so notebooks share the same `pro_service` / `fraud_rules`
implementation as the workshop API.

Convention: every Pro Mode notebook starts with

    from _lib import pro_service, fraud_rules, SAMPLES_DIR, REFERENCE_DATA_DIR
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
REPO_ROOT = _HERE.parents[3]
API_ROOT = REPO_ROOT / "apps" / "workshop" / "api"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

try:
    from dotenv import load_dotenv  # type: ignore

    _root_env = REPO_ROOT / ".env"
    if _root_env.exists():
        load_dotenv(_root_env)
except Exception:
    pass

from app.services import fraud_rules, pro_service  # noqa: E402

DEMO_ROOT = pro_service.PRO_DEMO_ROOT
SAMPLES_DIR = pro_service.SAMPLES_DIR
TEMPLATE_DIR = pro_service.TEMPLATE_DIR
REFERENCE_DATA_DIR = pro_service.REFERENCE_DATA_DIR
CU_OUTPUT_DIR = pro_service.CU_OUTPUT_DIR
