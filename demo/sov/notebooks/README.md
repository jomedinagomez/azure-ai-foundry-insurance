# SOV Extraction — Methodology

How we use Azure AI **Content Understanding** to extract Statements of Values from broker submissions, why the pipeline is shaped the way it is, and what we have learned from running it across 6 deliberately diverse templates.

---

## TL;DR

- One canonical **field schema** (account header + repeating `Locations[]`) lives in [`../reference/analyzer-templates/sov_extraction.json`](../reference/analyzer-templates/sov_extraction.json).
- We deploy **two analyzers** built from the same field schema and dispatch by file shape:
  - **`sovExtractV1`** — used for **PDFs** (`prebuilt-document` + `method: extract` + grounding boxes + per-field confidence).
  - **`sovGenerateV1`** — used for **Excel** AND for **per-image fan-outs** of embedded images (`prebuilt-document` + `method: generate`, no pixel grounding).
- A small set of fields with fixed value sets use **`method: classify`** with an enum (`Currency`, `Sprinklered`).
- **Four input shapes**, split across two notebooks:
  1. **PDF** ([`01_extract_sov.ipynb`](01_extract_sov.ipynb)) → one analyze call with the extract analyzer.
  2. **Plain Excel** ([`01_extract_sov.ipynb`](01_extract_sov.ipynb)) → one analyze call with the generate analyzer.
  3. **Excel with embedded images** ([`01_extract_sov.ipynb`](01_extract_sov.ipynb)) → one analyze call on the workbook **plus** one extra call per embedded image (same generate analyzer, `image/png` content type), then the `Locations[]` arrays are merged client-side.
  4. **`xlsx` via preflighted PDF → 800 DPI TIFF** ([`02_xlsx_via_pdf_tiff.ipynb`](02_xlsx_via_pdf_tiff.ipynb)) → preprocess the workbook into a multi-page TIFF and send it to the **same `sovExtractV1` analyzer used for PDFs**. Recovers grounding + per-field confidence + bounding boxes for spreadsheet inputs.
- The validator [`03_validate_extraction.ipynb`](03_validate_extraction.ipynb) compares each extraction against ground truth in [`../reference/expected-output/`](../reference/expected-output/) using a tolerant comparator (case, unicode dashes/quotes, placeholder strings, numeric/boolean coercion). It reads cached outputs from `../reference/cu-output/` (Approaches 1–3) and `../reference/cu-output-tiff800/` (Approach 4).

---

## The four extraction approaches

The same target schema is used in all four. What changes is **how** values get to the schema.

### Approach 1 — PDF (native or scanned)

`prebuilt-document` runs OCR + layout, then the **`extract`** method grounds each field to a pixel region on the rendered page. We get `valueString` / `valueNumber` plus a `spans` offset, a `source` bounding box, and a per-field confidence. Works for both digital and scanned PDFs.

```
attachments/04_summit_SOV.pdf  ->  sovExtractV1
```

### Approach 2 — Plain Excel (no embedded images)

The same `prebuilt-document` base. We switch to **`generate`** because Excel cells don't have stable pixel coordinates — `extract` returns `confidence: 1` on every field with no actual `valueString`. `generate` lets the LLM produce values directly from the structural representation. Confidence and grounding boxes are not returned, but we still get every field populated.

```
attachments/02_cascade_SOV.xlsx  ->  sovGenerateV1
```

### Approach 3 — Excel with embedded images (Pattern C: workbook + image fan-out, client-side merge)

When a workbook contains embedded images (an `xl/media/*.png` entry inside the `.xlsx` zip), CU's spreadsheet pipeline does **not** OCR them. Real brokers paste screenshots into SOVs all the time, so we handle it explicitly:

1. Run the workbook through `sovGenerateV1` — get the account fields and the locations table CU could see (everything except rows that exist only inside the embedded image).
2. Use Python's `zipfile` to enumerate every image under `xl/media/` in the `.xlsx`.
3. Run **the same** `sovGenerateV1` analyzer on each image with `content_type: image/png`. The image-call returns mostly-null account fields (it can't see them) but a populated `Locations[]` for the rows visible in the image.
4. **Merge** the location arrays client-side. Dedupe by `(LocationNumber, Street)`. Tag image-only rows with `_source: "image[N]"` so the validator can show provenance.

```
attachments/01_acme_SOV.xlsx
   ├─ workbook   -> sovGenerateV1   (account fields + 19 locations)
   └─ image #1   -> sovGenerateV1   (3 extra locations)
                                              ────────────────
                                              merged: 22 locations
```

**Why not Pro Mode?** Pro Mode in Content Understanding accepts multiple inputs in a single analyze call and consolidates them itself — conceptually a perfect fit. We tried it. Three blockers:

1. The GA `2025-11-01` ContentAnalyzer schema **has no `mode` field** — the GA service silently drops `mode: "pro"`. The November 2025 GA release notes confirm: *"The preview API doesn't carry forward Pro mode for cross-file analysis."*
2. The preview API (`2025-05-01-preview`) does support Pro Mode but is **region-limited** to `westus`, `swedencentral`, and `australiaeast`. Our workshop resource is in `eastus2` and the preview API returns `404 Preview API is not supported in this region.`.
3. Preview APIs are scheduled to be retired by July 15, 2026.

Pattern C ships today on GA, requires no preview opt-in, and produces a more honest production story: a thin orchestration layer fans out, merges, and tags provenance. When Pro Mode returns to GA we can collapse Approach 3 into a single call.

### Approach 4 — `xlsx` via preflighted PDF → 800 DPI TIFF (NEW)

The cleanest workaround for the limitation that `extract` doesn't work on raw `.xlsx`. We preprocess the workbook client-side into a multi-page TIFF and send that to the **same `sovExtractV1` analyzer used for PDFs** — the wire format changes, the analyzer doesn't.

```
attachments/01_acme_SOV.xlsx
   │
   ├─ (openpyxl)   page-setup preflight                  → .print-ready.xlsx
   ├─ (LibreOffice) headless convert to PDF              → .pdf
   ├─ (pypdfium2)  rasterize every page @ 800 DPI        → multi-page TIFF
   └─ (CU)         analyze_binary content_type=image/tiff→ sovExtractV1 payload
```

Three reasons this works where raw xlsx + `extract` doesn't:

1. **CU's Standard (Layout) pipeline** accepts PDFs and images but treats Office files as Minimal-tier. Sending xlsx as TIFF promotes it to the grounded pipeline. (Documented in [`feedback/underwriting/research_xlsx_extract.ipynb`](../../../feedback/underwriting/research_xlsx_extract.ipynb).)
2. **Vector PDFs of borderless tables** mis-merge adjacent rows in `prebuilt-layout`'s text-stream reader. Rasterizing forces the OCR path, which uses pure spatial geometry. (See [`BUG_REPORT.md`](../../../feedback/underwriting/research-output/pdfs/BUG_REPORT.md) for the full evidence.)
3. **The preflight is non-negotiable** — without `fitToWidth=1` + autofit columns + image-aware print area, the PDF is unreadable.

The preprocessing primitives live in [`../preprocess/`](../preprocess/) so the workshop app and the notebook share one implementation.

**Acme accuracy vs. ground truth: 100.0%** at 800 DPI — ties the production `generate` route while restoring grounded per-field confidences and bounding boxes that `generate` doesn't provide. Plus, the rasterized pages include the embedded "ADDITIONAL LOCATIONS" image so this approach **subsumes Pattern C** for xlsx-with-images inputs (no client-side merge needed).

---

## Why a few fields use `classify` instead of `extract` / `generate`

Two fields in the schema have a small fixed value set. For these we use `method: "classify"` with an explicit `enum`:

| Field | Enum | Why classify |
|---|---|---|
| `Currency` | `["USD", "CAD", "EUR", "GBP", "MXN", "AUD"]` | Brokers will write `"USD"`, `"USD (mostly)"`, `"$"`, `"American dollars"` — all of those should normalize to `USD`. Classify forces a single canonical token. |
| `Sprinklered` | `["Yes", "No"]` | Source says `"Yes"`, `"Y"`, checkbox marks, etc. Classify forces one of two tokens; the validator's `_norm()` then maps `"Yes"`→`True` and `"No"`→`False`. |

`classify` works the same way in both analyzer variants (extract and generate), so no per-format split is needed for these fields.

> **Cost-tuning alternative.** Both `classify` and `extract` call the LLM (CU treats both as generative features), so swapping them does *not* shrink LLM cost meaningfully. The only thing `classify` adds is **server-side enum validation**. If you want a leaner schema (every byte of every description ships as prompt tokens on every call), you can rewrite these two fields as `extract` and normalize values in post-processing — accuracy is unchanged on this corpus.

## Completion model — gpt-4.1-mini, not gpt-4.1

The analyzers declare `"models": { "completion": "gpt-4.1-mini" }`. An A/B on the 4 in-source samples (785 fields total) showed:

| Model | Cost (4 samples) | Accuracy |
|---|---:|---:|
| `gpt-4.1` | $0.3887 | 100% (785/785) |
| **`gpt-4.1-mini`** | **$0.1156** | **100% (785/785)** |

Mini is ~70% cheaper for identical accuracy. Re-run [`demo/sov/scripts/ab_model_compare.py`](../scripts/ab_model_compare.py) any time the schema or sample set changes materially.

---

## What ran end-to-end

The notebook [`01_extract_sov.ipynb`](01_extract_sov.ipynb) does these steps:

1. Loads the two analyzer templates from `reference/analyzer-templates/`.
2. Authenticates with the Foundry resource using `DefaultAzureCredential` (your `az login` session).
3. Idempotently creates each analyzer in the resource (`begin_create_analyzer`, reuses by id if it already exists).
4. Iterates every `.xlsx` and `.pdf` under `attachments/`.
5. Routes each file to the appropriate analyzer based on its suffix.
6. Caches the raw CU result JSON to `reference/cu-output/<stem>.json` so subsequent runs are offline (and cheap).

The notebook [`03_validate_extraction.ipynb`](03_validate_extraction.ipynb) consumes those cached outputs:

1. Discovers cached CU outputs and pairs each one with its expected-output JSON.
2. Flattens the CU payload (PascalCase + `{type, valueX, confidence}` wrappers) into the canonical snake_case schema used by ground truth.
3. Renders **two side-by-side DataFrames**: account-level fields, and one row per `(location_number, field)` for the repeating schedule.
4. Each row has a `match` column produced by a tolerant comparator (see below).

### Tolerant value comparison

The comparator does what a person would do when eyeballing the results:

- Strips & lowercases strings.
- Treats placeholder strings (`""`, `"-"`, `"—"`, `"n/a"`, `"none"`, `"null"`, `"tbd"`) as `None`.
- Normalizes Unicode dashes (em/en/minus/hyphen) and curly quotes to ASCII before comparing.
- Collapses runs of whitespace to a single space.
- Treats `"Yes"`, `"Y"`, `"true"`, `"sprinklered"` as `True`; `"No"`, `"N"`, `"false"`, `"unsprinklered"` as `False`.
- Parses numeric strings: `"1"` matches `1`, `"1,250,000"` matches `1250000`.
- `None == None` is `True`. Anything-vs-`None` is a real miss.

This way the `match` column reflects real extraction errors, not type / encoding / placeholder cosmetic differences.

---

## Findings from running 6 templates

Buckets, in priority order:

### 1. Real extraction gaps — fix at the source

| What | Where | Cause | Mitigation |
|---|---|---|---|
| Missing locations 20–22 in Acme | `01_acme_SOV.xlsx` | Three rows live inside an **embedded image** at the bottom of the worksheet. Excel pipeline doesn't OCR embedded picture objects. | Phase-2 enhancement: pre-extract embedded images via `openpyxl`, send each to a separate CU analyze call, merge with the main row set. Or convert XLSX → PDF first. |
| Coastal `TotalInsuredValue` returns the **US subtotal** instead of the **grand total** | `06_coastal_SOV.xlsx` | The mid-table subtotal row visually outranks the "Grand Total — Building Replacement Cost" row at the bottom. | Schema description was tightened to explicitly say "ALWAYS pick the bottom-most grand total covering ALL locations". Recommend also recomputing TIV downstream by `sum(loc.tiv)` and surfacing any discrepancy. |

### 2. Source-of-truth gaps — not a CU problem

| What | Where | Reality |
|---|---|---|
| Null account-level fields (DBA, mailing address, primary operations, etc.) | Cascade & Coastal xlsx | These templates simply do not include those fields. CU correctly returned null. In production we would fall back to the broker email body or ACORD form. |
| Optional location fields (`stories`, `protection_class`, `roof_year`, `flood_zone`) | Summit & Heartland PDFs | The PDF schedule table doesn't include those columns. Nothing to extract. |

### 3. Cosmetic diffs — handled by the comparator

| Pattern | Example | Status |
|---|---|---|
| Type drift | `LocationNumber` returned as `"1"` (string) but expected is `1` (int) | Resolved: schema now declares `type: number`; comparator parses numeric strings either way. |
| Boolean drift | `Sprinklered` returned `"Yes"` vs expected `true` | Resolved: schema now uses `classify` with `[true, false]`; comparator also normalizes `"Yes"`/`"No"`. |
| Casing | `BrokerName: "ATLANTIC SPECIALTY BROKERS"` vs `"Atlantic Specialty Brokers"` | Comparator does case-insensitive match. The verbatim-extracted value is a defensible LLM choice. |
| Trailing designations | `PreparedBy: "Sarah Whitfield"` vs `"Sarah Whitfield, ARM"` | Acceptable variance — the model picked the most prominent token. |

### 4. Format-specific oddities to be aware of

- **Multi-sheet Excel** (Magnolia: 4 tabs) — CU treats each sheet as an additional rendered page. The same analyzer pulled the account header from the Summary tab and the `Locations[]` array from the Locations tab cleanly. No client-side splitting required.
- **Embedded images in Excel** — extracted as figures in the markdown but **not** processed by the field extractor. This is the single largest gap for Acme.
- **Scanned PDF** (Heartland) — works well with the `extract` method; OCR + de-skew are handled by `prebuilt-document`. We see slightly lower confidence scores than on the native PDF (Summit) but values come through.
- **Messy broker spreadsheets** (Coastal: 3-row header, multi-row column headers, mid-table subtotals, label drift) — `generate` handles the layout fine; the only real loss is the TIV-grand-total selection issue, addressed above.

---

## What we would do next (deferred)

These are not implemented yet but follow naturally from the methodology above.

1. **Embedded-image extraction for `.xlsx`.** ✅ **Implemented** in [`02_xlsx_via_pdf_tiff.ipynb`](02_xlsx_via_pdf_tiff.ipynb) (Approach 4). The TIFF rasterization captures embedded images as part of the page, so the same `sovExtractV1` analyzer handles main schedule + image rows in one call. Approach 3 remains for environments where LibreOffice isn't available.
2. **TIV cross-check.** A post-processing step that computes `sum(building_value + bpp_value + bi_ee_value)` across locations and flags any case where the extracted `TotalInsuredValue` differs by more than, say, 1%.
3. **Field-presence reporting.** Track per-template which fields are populated vs null. Useful for the broker conversation ("your template doesn't include valuation date — please add").
4. **Confidence-based human-in-the-loop routing.** PDFs already return per-field confidence. Below threshold → review queue. Excel via `generate` doesn't return field-level confidence the same way — we would need to either add a CU step that re-validates, or use the LLM-backed `generate` analyzer's overall warning signals.
5. **Loss runs and ACORD documents.** Out of scope for this slot but would use additional analyzers with their own field schemas, dispatched the same way.

---

## File reference

| File | Purpose |
|---|---|
| [`../reference/analyzer-templates/sov_extraction.json`](../reference/analyzer-templates/sov_extraction.json) | Master schema. All `extract` for PDFs and TIFFs; `classify` for fixed-set fields. |
| [`../reference/analyzer-templates/sov_extraction_generate.json`](../reference/analyzer-templates/sov_extraction_generate.json) | Same schema with `extract` → `generate`. Used for `.xlsx` AND for per-image fan-outs in Approach 3. |
| [`../preprocess/`](../preprocess/) | Reusable preprocessing primitives used by Approach 4 and (later) by the workshop app: `apply_print_preflight`, `convert_libreoffice`, `rasterize_pdf_to_tiff`. |
| [`../reference/cu-output/`](../reference/cu-output/) | Cached CU response JSON for Approaches 1–3, one per attachment. |
| [`../reference/cu-output-tiff800/`](../reference/cu-output-tiff800/) | Cached CU response JSON for Approach 4, one per `.xlsx` attachment. |
| [`../reference/expected-output/`](../reference/expected-output/) | Ground truth from `seed_data.py`. |
| [`01_extract_sov.ipynb`](01_extract_sov.ipynb) | End-to-end extraction with the three-approach dispatcher (Approaches 1–3) + replay-from-cache. |
| [`02_xlsx_via_pdf_tiff.ipynb`](02_xlsx_via_pdf_tiff.ipynb) | Approach 4 — xlsx → preflight → PDF → TIFF@800 → `sovExtractV1`. |
| [`03_validate_extraction.ipynb`](03_validate_extraction.ipynb) | Offline side-by-side comparison with tolerant matching. Reads both `cu-output/` and `cu-output-tiff800/`. |
