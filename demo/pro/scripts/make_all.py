"""One-shot: generate every synthetic input PDF/PNG, the tampered estimate,
the reference policy, and stage both sample folders with manifest.json.

All inputs are locally generated — no external fetches.

Run from repo root:

    python demo/pro/scripts/make_all.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_damage_photo
import generate_claim_form
import generate_clean_estimate
import generate_police_report
import generate_policy
import seed_fraud_variant
import seed_samples


STEPS = [
    ("Reference policy PDF",           generate_policy.main),
    ("FNOL claim form PDF",            generate_claim_form.main),
    ("Police accident report PDF",     generate_police_report.main),
    ("Clean body-shop estimate PDF",   generate_clean_estimate.main),
    ("Damage photo PNG (CPSA v2 fetch)", fetch_damage_photo.main),
    ("Tampered estimate PDF (fraud)",  seed_fraud_variant.main),
    ("Stage sample folders",           seed_samples.main),
]


def main() -> int:
    n = len(STEPS)
    for i, (label, fn) in enumerate(STEPS, start=1):
        print(f"\n=== [{i}/{n}] {label} ===")
        rc = fn()
        if rc not in (0, None):
            return rc or 1
    print("\nAll Pro Mode demo assets generated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
