"""Fetch the damage photograph from the Microsoft Content Processing
Solution Accelerator v2 sample bundle.

We use the upstream synthetic image because it depicts realistic vehicle
damage that a generated raster diagram can't match. The other claim
documents (FNOL, police report, repair estimate) are generated locally
with narratives describing front-end collision damage that matches what
this photo shows.

Run from repo root:

    python demo/pro/scripts/fetch_damage_photo.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

UPSTREAM_URL = (
    "https://raw.githubusercontent.com/"
    "microsoft/content-processing-solution-accelerator/"
    "main/src/ContentProcessorAPI/samples/claim_date_of_loss/damage_photo.png"
)

DEST = Path(__file__).resolve().parent.parent / "source-data" / "generated" / "damage_photo.png"


def main() -> int:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists() and DEST.stat().st_size > 0:
        print(f"  [skip] {DEST.name} already present ({DEST.stat().st_size:,} bytes)")
        return 0
    try:
        print(f"  [get ] {DEST.name} <- {UPSTREAM_URL}")
        with urllib.request.urlopen(UPSTREAM_URL, timeout=60) as resp:  # nosec
            data = resp.read()
        DEST.write_bytes(data)
        print(f"  [ok  ] {DEST.name} ({len(data):,} bytes)")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
