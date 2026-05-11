# CU Layout — Bug report: row collisions in vector PDFs of borderless tables

**Submitted by:** SOV underwriting workshop team
**Date:** 2026-05-08
**API tier:** Azure Content Understanding GA (`2025-11-01`), `prebuilt-layout` and custom analyzer with `method=extract` on `prebuilt-document`
**Severity:** Functional regression — wrong row-to-row association on borderless tables, leading to data swapped between adjacent rows

---

## TL;DR

`prebuilt-layout` and `extract` mis-segment adjacent rows in vector
(text-stream) PDFs of borderless tables. The same content sent as a 600 DPI
TIFF — which forces the OCR path — segments correctly. We can reproduce on
demand; all artifacts (input xlsx, both PDFs, both TIFFs, both layout JSONs,
both extract payloads, ground-truth JSON) are in this repository alongside
this report.

This blocks our ability to ship the workshop demo's "Pattern A on xlsx"
flow without an extra raster-to-image step that costs ~17× payload size and
~2× latency vs. sending the vector PDF directly.

---

## What we expected

For a vector PDF that contains a tabular schedule, `prebuilt-layout` should
return one row per visual row. Underwriting SOVs frequently have **borderless
tables** where rows are separated by:

- whitespace
- alternating fill (zebra striping)
- the `Loc #` integer in column A

…not by drawn cell borders. A human reading the PDF has no trouble; the rows
are visually distinct.

## What actually happens

When we render the same xlsx to a vector PDF and send it to CU, two physically
distinct rows in the rendered table come back **merged into a single layout
cell**, with the values stacked using `<br>` separators **and the row order
inverted**:

```html
<td>19<br>18</td>
<td>1850 Old Mill Rd<br>445 Distribution Way</td>
<td>Birmingham<br>Atlanta</td>
<td>AL<br>GA</td>
<td>35211<br>30336</td>
<td>Frame<br>Non-Combustible</td>
<td>Warehouse - Legacy storage facility<br>Warehouse - Southeast distribution</td>
<td>1968<br>2009</td>
<td>85000<br>175000</td>
<td>$850,000<br>$15,800,000</td>
<td>$200,000<br>$2,900,000</td>
<td>$100,000 Acquired 2024 - values pending appraisal<br>$1,500,000</td>
```

Source rows (open `01_acme_SOV.print-ready.xlsx` to verify):

```
row 38: 18 | 1850 Old Mill Rd       | Birmingham   | AL | 35211 | Frame           | …
row 39: 19 | 445 Distribution Way   | Atlanta      | GA | 30336 | Non-Combustible | …
```

So in the PDF route loc 18 ends up with loc 19's address/values and vice
versa. When the same content is sent as a 600 DPI multi-page TIFF (forcing
CU's OCR path), the rows segment correctly and every value lines up with
ground truth.

## Why we believe this is a service-side issue

We tried a series of client-side mitigations on the source xlsx before
re-rendering. None resolve the collision in the vector-PDF route, but each
data point narrows the cause:

| Variant | Layout-md % of xlsx baseline | Loc-cell mismatches vs ground truth | Behavior |
|---|---|---|---|
| Vector PDF, no preflight | 62.0% | 33 (rows 18/19 swapped + others) | row order wrong |
| Vector PDF + page-fit preflight | 56.7% | 25 | rows 18/19 still swapped |
| Vector PDF + autofit columns | 56.7% | 25 | unchanged |
| Vector PDF + reset row heights | 56.7% | 25 | unchanged |
| Vector PDF + heavy black borders | 75.4% | 0 (perfect) | hides the bug — but cosmetically wrong |
| Vector PDF + Excel print gridlines | 88.1% | 10 | partial fix |
| **Vector PDF, natural defaults** | **56.7%** | **25** | **→ this report's bug** |
| **TIFF 600 DPI (OCR path)** | n/a | **0 (perfect)** | the workaround we shipped |

`prebuilt-layout`'s text-stream-based row grouping appears to use
Y-coordinate proximity. Without explicit cell borders, rows whose Y centers
are close (which is the natural look of a printed Excel table) get bundled
into one logical row. Our hypothesis: the layout analyzer reads the PDF
content stream's `Tj`/`TJ` operators in the order the renderer emitted them,
not in spatial top-to-bottom order, then groups them by proximity and emits
the first cluster's order as-is — which is why we see the row order *inverted*.

## Reproduction

### Inputs (all in this folder)

| File | Description |
|---|---|
| `01_acme_SOV.print-ready.xlsx` | The preflighted xlsx fed to LibreOffice |
| `02_libreoffice_preflight/01_acme_SOV.print-ready.pdf` | Vector PDF (134 KB) — **the bug's input** |
| `02_libreoffice_preflight/01_acme_SOV.print-ready.layout.json` | `prebuilt-layout` raw output that shows the merged `<td>19<br>18</td>` cell |
| `02_libreoffice_preflight.extract.json` | Custom analyzer (`sovExtractV1`) output where loc 18 and 19 are swapped |
| `04_libreoffice_tiff_600/01_acme_SOV.print-ready.tiff` | 600 DPI multi-page TIFF (2.4 MB) — the workaround |
| `04_libreoffice_tiff_600.extract.json` | Same analyzer, correct row segmentation |
| Ground truth: [`demo/sov/reference/expected-output/01_acme.json`](../../../demo/sov/reference/expected-output/01_acme.json) |

### Direct repro (no notebook)

```bash
# 1. prebuilt-layout on the vector PDF — see the row collision in markdown
curl -X POST "${ENDPOINT}/contentunderstanding/analyzers/prebuilt-layout:analyze?api-version=2025-11-01" \
  -H "Content-Type: application/pdf" \
  --data-binary @02_libreoffice_preflight/01_acme_SOV.print-ready.pdf
# search the resulting markdown for "19<br>18"

# 2. same input as TIFF — row order is correct
curl -X POST "${ENDPOINT}/contentunderstanding/analyzers/prebuilt-layout:analyze?api-version=2025-11-01" \
  -H "Content-Type: image/tiff" \
  --data-binary @04_libreoffice_tiff_600/01_acme_SOV.print-ready.tiff
```

### End-to-end repro (with our matrix)

[`research_xlsx_to_pdf.ipynb`](../../research_xlsx_to_pdf.ipynb) runs the full
pipeline (preflight → LibreOffice convert → optional rasterize → CU layout +
extract → diff against ground truth). On Acme:

| Variant | Overall accuracy vs ground truth |
|---|---|
| Vector PDF, natural defaults | 91.3% — fails on 25 location-field cells |
| TIFF 600 DPI | 99.7% — only 1 OCR glitch (a parenthesis on a phone number) |

## Code references

The exact functions producing the artifacts above:

- `apply_print_preflight` in [`research_xlsx_to_pdf.ipynb`](../../research_xlsx_to_pdf.ipynb) — page-setup preflight applied to the source xlsx.
- `convert_libreoffice` in the same notebook — `soffice --headless --convert-to pdf:calc_pdf_Export`. Vector PDF.
- `rasterize_pdf_to_tiff` in the same notebook — `pypdfium2` render at 600 DPI then `Pillow` save as multi-page LZW TIFF. OCR-path workaround.
- `run_sov_extract_on_pdf` in the same notebook — sets `Content-Type` from suffix, runs the same `sovExtractV1` analyzer template against either PDF or TIFF.

## Asks of the CU team

1. **Add a `forceOcr` (or equivalent) request parameter** on `prebuilt-layout`
   and on custom analyzers that derive from it, so callers can opt out of the
   text-stream path when their PDF is a borderless table. This is the
   cleanest fix — keep the small fast vector PDF on the wire, get correct
   row segmentation back. Document Intelligence v3.1 had a similar concept
   (`pages` / `forceOnePageOnly`) so the precedent exists.

2. **Investigate the Y-proximity row grouping heuristic** for borderless
   tables. The current threshold appears too loose for tightly-packed
   schedules. A threshold tied to median row stride rather than absolute
   pixels would handle this case without harming sparse layouts.

3. **Order text-stream emissions spatially before grouping.** The fact that
   the merged cell shows `19` *before* `18` even though row 18 is physically
   above row 19 in the PDF suggests the analyzer is trusting content-stream
   order. Sorting by `(y, x)` of bounding box centers before clustering
   would eliminate the *order inversion* even if the merge bug remained.

4. **Fail loudly when row segmentation is suspect.** Today the only signal
   that something went wrong is the `<br>` separator inside a `<td>`. A
   structured warning (`_meta.warnings: [{ code: "PossibleRowMerge", page: 1, ... }]`)
   would let downstream pipelines detect the failure mode without parsing
   markdown for `<br>`.

## Workaround we shipped

We rasterize the LibreOffice-exported PDF into a 600 DPI multi-page TIFF
(`pypdfium2` → `Pillow` LZW TIFF) before calling CU. This forces the OCR
path and resolves the row collisions but increases the per-document payload
~17× and adds ~2 s per call. Acceptable for the workshop, painful at
production scale — hence this bug report.

## Open questions

- Is there an undocumented header / config flag we're missing that would
  trigger OCR on a vector PDF? We tried `enableOcr` and
  `estimateFieldSourceAndConfidence` on the custom analyzer; neither
  changed the layout segmentation.
- Does `prebuilt-documentSearch` use the same row-grouping logic? It returned
  the same 12,380-char markdown on the original xlsx as `prebuilt-layout`,
  so we suspect the layout pipeline is shared.
- Does this also affect Word or PowerPoint inputs that contain borderless
  tables? We have not tested.

## Contact

File any follow-up questions on the SOV underwriting workshop issue tracker;
notebook owners are tagged in `feedback/underwriting/README.md`.
