# Azure AI Content Understanding — Underwriting Scenario Feedback

Field observations from building an SOV (Statement of Values) extraction pipeline
for commercial property underwriting submissions. See [limitations.ipynb](limitations.ipynb)
for reproducible examples.

## Scope

- 6 sample submissions across 3 input modes:
  - PDF (`method=extract`, `baseAnalyzerId=prebuilt-document`)
  - `.xlsx` workbook (`method=generate`)
  - `.xlsx` + embedded images (Pattern C client-side fan-out + merge)
- Schema: account-level metadata + `Locations[]` array (address, COPE, TIV, etc.)

## Limitation categories

1. **File-format constraints** — `.xlsx` cannot use `method=extract` (silently
   returns empty fields with `confidence: 1` — see
   [research_xlsx_extract.ipynb](research_xlsx_extract.ipynb) for documented
   evidence and reproduction); no native multi-modal call for workbook +
   embedded images.
2. **Response-length / output-size limits** — long arrays and free-text fields
   silently truncate.
3. **Cell-level vs. text-level extraction** — `generate` on xlsx returns raw cell
   values, mishandles merged cells, swaps row/column orientation, and gives no
   structural grounding.
4. **Row collisions on borderless tables in vector PDFs** — `prebuilt-layout`
   merges and inverts adjacent rows when a vector PDF table has no drawn cell
   borders. Forcing the OCR path (rasterized TIFF) is the only reliable
   workaround we found. **See the dedicated bug report:**
   [`research-output/pdfs/BUG_REPORT.md`](research-output/pdfs/BUG_REPORT.md).

See the notebook for code samples, observed payloads, and mitigations applied
in this repo.

## For Engineering: bug reports & repro packages

Each report in this folder is a self-contained packet — input, output, code,
ground truth, and step-by-step repro — that an engineer can read in 10
minutes and reproduce in 30. Add new reports by following the same shape.

| Report | Service area | Severity | Repro notebook | Workaround |
|---|---|---|---|---|
| [Row collisions in vector PDFs of borderless tables](research-output/pdfs/BUG_REPORT.md) | `prebuilt-layout`, custom `extract` analyzers | Functional regression — wrong data attached to wrong rows | [research_xlsx_to_pdf.ipynb](research_xlsx_to_pdf.ipynb) | 600 DPI TIFF (~17× larger payload, ~2× latency) |
| [`extract` on `.xlsx` returns empty values with `confidence: 1`](research_xlsx_extract.ipynb) | Custom analyzers with `method=extract` on Office formats | Silent functional failure | [research_xlsx_extract.ipynb](research_xlsx_extract.ipynb) | Use `method=generate` for xlsx, or convert xlsx → PDF/TIFF first |

### Code & input artifacts

All notebook helpers we use across the bug repros live in:
- [research_xlsx_to_pdf.ipynb](research_xlsx_to_pdf.ipynb) — `apply_print_preflight`,
  `convert_libreoffice`, `rasterize_pdf_to_tiff`, `run_sov_extract_on_pdf`,
  `measure_pdf_layout`. These are pure functions that take a `Path` and
  return a `Path` or `dict`; copy them into a script for any standalone
  repro.
- [research_xlsx_extract.ipynb](research_xlsx_extract.ipynb) — variant matrix
  for the `extract`-on-xlsx silent-empty bug.
- [research-output/pdfs/](research-output/pdfs/) — actual PDF and TIFF
  payloads we sent to CU plus the JSON we got back, so engineering can
  re-test against the same bytes.
- Source workbook: [`demo/sov/attachments/01_acme_SOV.xlsx`](../../demo/sov/attachments/01_acme_SOV.xlsx)
- Ground truth: [`demo/sov/reference/expected-output/01_acme.json`](../../demo/sov/reference/expected-output/01_acme.json)
- Workshop validator (port of the notebook validator): [`apps/workshop/api/app/services/sov_service.py`](../../apps/workshop/api/app/services/sov_service.py) — function `validate(payload, expected)` is what the accuracy numbers in the bug reports are measured against.

### How to add a new bug report

1. Drop your evidence (input file, raw CU response, screenshot if
   relevant) into `research-output/<topic>/`.
2. Author a `BUG_REPORT.md` next to those artifacts following the same
   shape as the existing ones: TL;DR, what we expected, what actually
   happens, why we believe it's service-side (with a comparison matrix),
   reproduction steps (curl + notebook), code refs, asks of the CU team,
   workaround we shipped, open questions.
3. Add a row to the **bug reports & repro packages** table above.
4. If the bug warrants a new "asks for the service" line item, add it
   to [limitations.ipynb](limitations.ipynb) section 5.

