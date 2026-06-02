"""Quick smoke-test for the pro-mode fraud flow. Run with the venv:

    .\.venv\Scripts\python.exe demo\pro\notebooks\_smoke_fraud.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import pro_service

manifest, files = pro_service.load_sample("claim_auto_collision_fraud")
print(f"Analyzing {len(files)} files (this runs BOTH analyzers, ~90s)...")
r = pro_service.analyze_fraud(files, sample_id="claim_auto_collision_fraud")

print()
print(f"Risk score        : {r.risk_score}/100  band={r.risk_band.upper()}")
print(f"Rule signals      : {len(r.rule_signals)}")
print(f"CU signals        : {len(r.cu_signals)}")
print(f"Overall CU rating : {r.fields.overall_fraud_indication}")
print()
for s in [*r.rule_signals, *r.cu_signals]:
    print(f"  [{s.severity:6s}] {s.rule_id}")
    print(f"      {s.evidence[:140]}")
