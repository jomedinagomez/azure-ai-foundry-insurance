"""Diagnose where CU's LLM-input tokens are going for a single SOV run.

Token estimate uses the rule-of-thumb 4 chars/token (close enough for English
+ JSON). The real tokenizer would give a tighter number, but this is fine for
"is the schema or the OCR text the bigger problem" diagnostics.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "demo" / "sov" / "reference" / "analyzer-templates" / "sov_extraction.json"


def est_tokens(s: str) -> int:
    return max(1, len(s) // 4)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# ── 1. Schema size ─────────────────────────────────────────────────────────
schema_text = SCHEMA.read_text(encoding="utf-8")
schema_json = json.loads(schema_text)

section("Analyzer schema (every description = prompt tokens on every call)")
print(f"Full schema file: {len(schema_text):>6,} chars  ~{est_tokens(schema_text):,} tokens")

# Pull every description out and rank by size
descriptions: list[tuple[str, str, int]] = []  # (path, text, chars)
def walk(obj, path: str) -> None:
    if isinstance(obj, dict):
        if "description" in obj and isinstance(obj["description"], str):
            descriptions.append((path, obj["description"], len(obj["description"])))
        for k, v in obj.items():
            walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{path}[{i}]")

walk(schema_json, "$")
descriptions.sort(key=lambda x: -x[2])
print(f"\nFields with descriptions: {len(descriptions)}")
print(f"Total description chars: {sum(d[2] for d in descriptions):,}  ~{est_tokens(''.join(d[1] for d in descriptions)):,} tokens")
print("\nTop 10 longest descriptions:")
for path, text, n in descriptions[:10]:
    print(f"  {n:>5} chars  {path}")

# ── 2. OCR markdown size from a recent run ─────────────────────────────────
section("OCR markdown that CU feeds to the LLM (per page)")
runs_dir = ROOT / "apps" / "workshop" / "api" / ".runs"
latest_jsons = []
for run in runs_dir.iterdir() if runs_dir.exists() else []:
    pass  # CU payload isn't saved per-run; fall back to the canonical cache

cache_dir = ROOT / "demo" / "sov" / "reference" / "cu-output-tiff800"
for p in sorted(cache_dir.glob("*.json")):
    payload = json.loads(p.read_text(encoding="utf-8"))
    contents = payload.get("contents") or []
    if not contents:
        continue
    md = (contents[0] or {}).get("markdown") or ""
    print(f"  {p.name:30s} markdown: {len(md):>6,} chars  ~{est_tokens(md):,} tokens  ({len(contents)} content blocks)")

# ── 3. The math ────────────────────────────────────────────────────────────
section("How the per-call LLM input is composed (rough)")
print("Each generative analyze call sends roughly:")
print("  schema (descriptions + names + structure) + page markdown + system prompt")
print("CU may make multiple LLM calls per page (the 'completion calls' counter).")
print("With source grounding + confidence enabled, expect ~2x multiplier.")
