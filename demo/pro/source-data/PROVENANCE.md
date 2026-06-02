# Source data provenance

All input PDFs and PNGs under this folder are **locally generated synthetic
documents** produced by the scripts in `demo/pro/scripts/`. There are no
external downloads.

Generated assets:
- `generated/claim_form.pdf`         — `scripts/generate_claim_form.py`
- `generated/police_report.pdf`      — `scripts/generate_police_report.py`
- `generated/repair_estimate.pdf`    — `scripts/generate_clean_estimate.py` (clean)
- `generated/damage_photo.png`       — `scripts/generate_damage_photo.py`
- Reference policy lives one level up at `../reference-data/auto_policy.pdf`
  — `scripts/generate_policy.py`.
- The tampered estimate for the fraud scenario is written directly into
  `../samples/claim_auto_collision_fraud/repair_estimate.pdf` by
  `scripts/seed_fraud_variant.py`.

All documents are synthetic. Names, addresses, policy numbers, VIN, license
plates, license numbers, and email addresses are fictional. Any resemblance
to real persons or businesses is coincidental.

To regenerate everything from scratch:
```powershell
python demo/pro/scripts/make_all.py
```
The pipeline is idempotent and safe to re-run.
