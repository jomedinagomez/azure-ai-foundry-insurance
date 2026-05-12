"""A/B compare CU completion-model cost+accuracy across the 4 in-source samples.

Runs the current analyzer (already deployed) against all 4 samples, reports
per-sample and combined: total cost, LLM token usage, in-source field count,
and validation accuracy. Pair with `confidence_buckets.py` for the deeper
confidence-bucket breakdown.

Usage:
    # 1. Edit sov_extraction.json -> models.completion = "gpt-4.1"
    # 2. Push and run: python demo/sov/scripts/ab_model_compare.py | Tee A.txt
    # 3. Edit -> "gpt-4.1-mini", push, re-run | Tee B.txt
    # 4. Compare A.txt vs B.txt
"""
import requests

SAMPLES = [
    "01_acme_SOV.xlsx",
    "02_cascade_SOV.xlsx",
    "03_magnolia_SOV.xlsx",
    "06_coastal_SOV.xlsx",
]

API = "http://localhost:8000"

print(f"{'sample':28s} {'total $':>10s} {'in tok':>10s} {'out tok':>10s} {'in-src':>8s} {'match':>8s}")
print("-" * 80)

agg = {"cost": 0.0, "in_tokens": 0, "out_tokens": 0, "in_src": 0, "matched": 0}

for s in SAMPLES:
    ex = requests.post(f"{API}/sov/extract/pipeline",
                       json={"sample_name": s, "pipeline_id": "xlsx_via_pdf_tiff"},
                       timeout=600).json()
    val = requests.post(f"{API}/sov/validate", json={"sample_name": s}, timeout=120).json()

    cost = ex["meta"].get("cost") or {}
    inputs = cost.get("inputs") or {}
    total = float(cost.get("total", 0.0))
    in_tok = int(inputs.get("llm_input_tokens", 0))
    out_tok = int(inputs.get("llm_output_tokens", 0))

    # In-source field count (account + locations)
    in_src = 0
    matched = 0
    for d in val.get("account") or []:
        if d.get("in_source"):
            in_src += 1
            if d.get("match"):
                matched += 1
    for d in val.get("locations") or []:
        if d.get("in_source"):
            in_src += 1
            if d.get("match"):
                matched += 1

    print(f"{s:28s} ${total:>9.4f} {in_tok:>10,} {out_tok:>10,} {in_src:>8d} {matched:>8d}")
    agg["cost"] += total
    agg["in_tokens"] += in_tok
    agg["out_tokens"] += out_tok
    agg["in_src"] += in_src
    agg["matched"] += matched

print("-" * 80)
acc = (agg["matched"] / agg["in_src"] * 100) if agg["in_src"] else 0
print(
    f"{'TOTAL (4 samples)':28s} ${agg['cost']:>9.4f} "
    f"{agg['in_tokens']:>10,} {agg['out_tokens']:>10,} "
    f"{agg['in_src']:>8d} {agg['matched']:>8d}  ({acc:.2f}% acc)"
)
