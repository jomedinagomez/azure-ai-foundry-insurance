"""Confidence-bucket analysis across the 4 in-source xlsx SOV samples.

Runs the xlsx_via_pdf_tiff pipeline + /sov/validate for each sample,
counts every account + location field by its confidence bucket, and
cross-tabulates with whether each field matched ground truth. Used to
source numbers for the Hanover SOV demo closing slide
("confidence-to-automation matrix").
"""
import requests

SAMPLES = [
    "01_acme_SOV.xlsx",
    "02_cascade_SOV.xlsx",
    "03_magnolia_SOV.xlsx",
    "06_coastal_SOV.xlsx",
]


def bucket(v):
    if v is None:
        return "none"
    if v > 0.95:
        return "high"
    if v >= 0.70:
        return "mid"
    return "low"


def empty():
    return {b: {"count": 0, "matched": 0} for b in ("high", "mid", "low", "none")}


combined = empty()
per_sample = {}

for s in SAMPLES:
    ex = requests.post(
        "http://localhost:8000/sov/extract/pipeline",
        json={"sample_name": s, "pipeline_id": "xlsx_via_pdf_tiff"},
        timeout=600,
    ).json()
    val = requests.post(
        "http://localhost:8000/sov/validate",
        json={"sample_name": s},
        timeout=120,
    ).json()

    # Build a lookup of (scope, key, loc_key) -> matched bool for in-source
    # fields only. Out-of-source fields are skipped (we can't verify them).
    matched_lookup = {}
    for d in val.get("account") or []:
        if d.get("in_source"):
            matched_lookup[("account", d["field"], None)] = d.get("match", False)
    for d in val.get("locations") or []:
        if d.get("in_source"):
            matched_lookup[("location", d["field"], d.get("location_key"))] = (
                d.get("match", False)
            )

    ps = empty()

    # Account fields
    for k, v in (ex.get("account_confidence") or {}).items():
        b = bucket(v)
        key = ("account", k, None)
        if key not in matched_lookup:
            continue  # out-of-source — skip
        ps[b]["count"] += 1
        if matched_lookup[key]:
            ps[b]["matched"] += 1

    # Location fields — align by location_number to validation's location_key.
    locs = ex.get("locations") or []
    locs_conf = ex.get("locations_confidence") or []
    for i, conf in enumerate(locs_conf):
        loc_num = (locs[i] or {}).get("location_number") if i < len(locs) else None
        for k, v in (conf or {}).items():
            b = bucket(v)
            key = ("location", k, loc_num)
            if key not in matched_lookup:
                continue
            ps[b]["count"] += 1
            if matched_lookup[key]:
                ps[b]["matched"] += 1

    per_sample[s] = ps
    for b in combined:
        combined[b]["count"] += ps[b]["count"]
        combined[b]["matched"] += ps[b]["matched"]

print("=== Per-sample (in-source fields only) ===")
for s, ps in per_sample.items():
    tot = sum(ps[b]["count"] for b in ps)
    print(f"\n{s}: in-source fields = {tot}")
    for b in ("high", "mid", "low", "none"):
        c = ps[b]["count"]
        m = ps[b]["matched"]
        acc = (m / c * 100) if c else 0
        print(f"  {b:>5s}: {c:4d}  matched={m:4d}  accuracy={acc:5.1f}%")

print("\n=== Combined (all 4 samples) ===")
total = sum(combined[b]["count"] for b in combined)
total_matched = sum(combined[b]["matched"] for b in combined)
print(f"total in-source fields: {total}")
print(f"total matches:          {total_matched}")
print(f"overall accuracy:       {total_matched / total * 100:.2f}%\n")
labels = {
    "high": "> 0.95     (auto-approve candidate)",
    "mid":  "0.70-0.95  (secondary review)",
    "low":  "< 0.70     (manual review)",
    "none": "null       (not extracted)",
}
for b in ("high", "mid", "low", "none"):
    c = combined[b]["count"]
    m = combined[b]["matched"]
    pct = (c / total * 100) if total else 0
    acc = (m / c * 100) if c else 0
    print(f"  {labels[b]:38s} {c:5d}  ({pct:5.1f}% of fields)  accuracy={acc:5.1f}%")
