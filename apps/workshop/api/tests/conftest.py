"""Pytest config — ensure api/ is on sys.path and don't walk above it."""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
API_ROOT = HERE.parent
sys.path.insert(0, str(API_ROOT))

collect_ignore_glob = []
