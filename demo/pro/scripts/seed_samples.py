"""Stage the two sample folders by copying locally-generated source files
and writing per-sample manifest.json files.

Run from repo root after generators (or via make_all.py):

    python demo/pro/scripts/seed_samples.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_GEN = ROOT / "source-data" / "generated"
SAMPLES = ROOT / "samples"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_policy import POLICY_FACTS  # noqa: E402
from generate_claim_form import FNOL_FACTS  # noqa: E402
from generate_clean_estimate import ESTIMATE_FACTS as CLEAN_ESTIMATE_FACTS, GRAND_TOTAL as CLEAN_TOTAL  # noqa: E402
from seed_fraud_variant import ESTIMATE_FACTS as TAMPERED_FACTS, GRAND_TOTAL as TAMPERED_TOTAL  # noqa: E402


REQUIRED_GENERATED = [
    "claim_form.pdf",
    "police_report.pdf",
    "repair_estimate.pdf",
    "damage_photo.png",
]


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    shutil.copy2(src, dst)


def _check_sources() -> list[str]:
    return [n for n in REQUIRED_GENERATED if not (SRC_GEN / n).exists()]


def _stage_clean() -> Path:
    target = SAMPLES / "claim_auto_collision"
    for name in REQUIRED_GENERATED:
        _copy(SRC_GEN / name, target / name)

    manifest = {
        "id": "claim_auto_collision",
        "title": "Auto collision — complete claim package",
        "scenario": "claims",
        "loss_type": "Auto collision",
        "description": (
            "First Notice of Loss for a single-vehicle collision at an "
            "intersection. Package includes a fully synthetic FNOL claim "
            "form, a Springfield PD traffic crash report, a body-shop "
            "repair estimate, and an annotated damage photograph. All "
            "documents are internally consistent and consistent with the "
            "reference policy (auto_policy.pdf)."
        ),
        "claimant": POLICY_FACTS["named_insured"],
        "policy_number": POLICY_FACTS["policy_number"],
        "vin": POLICY_FACTS["vin"],
        "vehicle": POLICY_FACTS["vehicle"],
        "date_of_loss": FNOL_FACTS["date_of_loss"],
        "claim_number": FNOL_FACTS["claim_number"],
        "estimated_total_usd": CLEAN_TOTAL,
        "files": [
            {"name": "claim_form.pdf", "kind": "fnol", "media_type": "application/pdf"},
            {"name": "police_report.pdf", "kind": "police_report", "media_type": "application/pdf"},
            {"name": "repair_estimate.pdf", "kind": "repair_estimate", "media_type": "application/pdf"},
            {"name": "damage_photo.png", "kind": "damage_photo", "media_type": "image/png"},
        ],
        "expected_signals": [],
        "expected_risk_score_range": [0, 25],
        "source": {
            "provider": "Locally generated synthetic PDFs (reportlab) + damage_photo.png fetched from Microsoft CPSA v2.",
            "generator_scripts": [
                "demo/pro/scripts/generate_claim_form.py",
                "demo/pro/scripts/generate_police_report.py",
                "demo/pro/scripts/generate_clean_estimate.py",
                "demo/pro/scripts/fetch_damage_photo.py",
            ],
        },
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return target


def _stage_fraud() -> Path:
    target = SAMPLES / "claim_auto_collision_fraud"
    for name in ("claim_form.pdf", "police_report.pdf", "damage_photo.png"):
        _copy(SRC_GEN / name, target / name)

    tampered = target / "repair_estimate.pdf"
    if not tampered.exists():
        raise SystemExit(
            "Tampered repair_estimate.pdf is missing. "
            "Run `python demo/pro/scripts/seed_fraud_variant.py` first."
        )

    manifest = {
        "id": "claim_auto_collision_fraud",
        "title": "Auto collision — fraud-seeded variant",
        "scenario": "fraud",
        "loss_type": "Auto collision (suspected fraud)",
        "description": (
            "Same FNOL claim form, police report, and damage photograph as "
            "the clean scenario, but the repair estimate has been replaced "
            "with a freshly-rendered body-shop document containing three "
            "deliberate inconsistencies: inflated grand total exceeding the "
            "policy collision sub-limit, estimate date preceding the date "
            "of loss on the FNOL, and a VIN typo against the policy "
            "declarations."
        ),
        "claimant": POLICY_FACTS["named_insured"],
        "policy_number": POLICY_FACTS["policy_number"],
        "vin": POLICY_FACTS["vin"],
        "vehicle": POLICY_FACTS["vehicle"],
        "date_of_loss": FNOL_FACTS["date_of_loss"],
        "claim_number": FNOL_FACTS["claim_number"],
        "estimated_total_usd": TAMPERED_TOTAL,
        "files": [
            {"name": "claim_form.pdf", "kind": "fnol", "media_type": "application/pdf"},
            {"name": "police_report.pdf", "kind": "police_report", "media_type": "application/pdf"},
            {"name": "repair_estimate.pdf", "kind": "repair_estimate",
             "media_type": "application/pdf", "tampered": True},
            {"name": "damage_photo.png", "kind": "damage_photo", "media_type": "image/png"},
        ],
        "expected_signals": [
            {
                "rule_id": "TOTALS_EXCEED_SUBLIMIT",
                "severity": "high",
                "evidence": (
                    f"Estimate grand total ${TAMPERED_TOTAL:,.2f} exceeds policy "
                    f"collision sub-limit ${POLICY_FACTS['limit_collision_sublimit']:,}."
                ),
            },
            {
                "rule_id": "DATE_IMPLAUSIBLE",
                "severity": "high",
                "evidence": (
                    f"Estimate date {TAMPERED_FACTS['estimate_date']} precedes the "
                    f"date of loss {FNOL_FACTS['date_of_loss']} reported on the FNOL."
                ),
            },
            {
                "rule_id": "VIN_MISMATCH",
                "severity": "medium",
                "evidence": (
                    f"VIN on estimate ({TAMPERED_FACTS['vin_tampered']}) does not "
                    f"match policy VIN ({POLICY_FACTS['vin']})."
                ),
            },
        ],
        "expected_risk_score_range": [70, 95],
        "source": {
            "provider": "Locally generated synthetic PDFs (reportlab) + damage_photo.png fetched from Microsoft CPSA v2.",
            "generator_scripts": [
                "demo/pro/scripts/generate_claim_form.py",
                "demo/pro/scripts/generate_police_report.py",
                "demo/pro/scripts/seed_fraud_variant.py",
                "demo/pro/scripts/fetch_damage_photo.py",
            ],
        },
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return target


def main() -> int:
    missing = _check_sources()
    if missing:
        print(f"Source bundle missing files in {SRC_GEN}: {missing}", file=sys.stderr)
        print("Run `python demo/pro/scripts/make_all.py` to generate them.", file=sys.stderr)
        return 1
    c = _stage_clean()
    print(f"Staged {c}")
    f = _stage_fraud()
    print(f"Staged {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
