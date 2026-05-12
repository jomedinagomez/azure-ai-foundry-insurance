# SOV Demo — CL & Specialty Underwriting Workshop

> **Slot:** Noon–12:15pm · **Demo lead:** Jose Medina Gomez
> **Goal:** Show Azure AI Foundry **Content Understanding** ingesting realistic broker SOV submissions across **6 different template formats**, normalizing to a single schema, flagging anomalies, and producing a ranked risk view — directly addressing the typical "30+ template variations" concern from carrier intake teams.

> **Demo lives in [`apps/workshop/`](../../apps/workshop/) — the "Insurance Workbench" app.**
> Use it to drive the live portion of the demo: pick a sample → click Run →
> visualizer with field overlays + per-run cost pill + 100% validation
> against ground truth. Notebooks below (`notebooks/`) cover the deeper
> methodology and the four extraction approaches.

---

## What's in this folder

```
demo/sov/
├── emails/                     # 6 broker submission .eml files (open in Outlook)
│   └── signatures/             # broker logo PNGs (embedded inline in HTML signatures)
├── attachments/                # the 6 SOVs (4 .xlsx + 2 .pdf)
├── reference/
│   ├── target-schema.json      # canonical normalized SOV schema
│   ├── benchmarks.csv          # $/sqft benchmarks for valuation reasonability
│   └── expected-output/        # ground-truth normalized JSON (one per account)
└── scripts/                    # generators (regenerate everything from seed data)
    ├── requirements.txt
    ├── seed_data.py            # SINGLE SOURCE OF TRUTH for all 6 accounts
    ├── generate_logos.py
    ├── generate_excel.py
    ├── generate_pdf.py
    ├── generate_emails.py
    └── make_all.py             # runs the full pipeline
```

## Regenerating the assets

```powershell
cd demo/sov/scripts
pip install -r requirements.txt
python make_all.py
```

---

## The 6 Submissions (one per broker, one per template style)

| # | Insured (fictional)              | Broker                          | Template style                                              | Key anomaly the demo flags                                              |
|---|----------------------------------|---------------------------------|-------------------------------------------------------------|-------------------------------------------------------------------------|
| 1 | **Acme Manufacturing & Distribution** *(HERO)* | Sterling Risk Partners          | Excel — header block + table + merged cells + embedded image | 3 extra locations only visible in embedded image; flat-duplicate values; under-valuation outlier |
| 2 | Cascade Cold Storage             | Pacific Northwest Brokers       | Excel — clean flat table (baseline)                          | Massive under-valuation on Loc 5 ($2.50/sqft cold storage)              |
| 3 | Magnolia Hospitality Group       | Crescent Insurance Services     | Excel — multi-sheet (Summary / Locations / CAT / Notes)      | 62% of TIV in Gulf Coast hurricane zone; cross-sheet label inconsistency |
| 4 | Summit Outdoor Retail            | Rocky Mountain Brokerage        | Native PDF + footnotes                                       | Indoor firearms range buried at Loc 8 → "shooting" flag                 |
| 5 | Heartland Agri-Processors        | Prairie State Insurance Agency  | Scanned PDF (skewed, JPEG-compressed)                        | Missing ZIP / year built; PO Box mailing address; margin annotation     |
| 6 | Coastal Marine Services          | Atlantic Specialty Brokers      | Messy broker Excel (multi-row headers, mid-table totals)     | Mixed currency (CAD location); column label drift across the sheet      |

All 6 normalize to the **same target schema** (`reference/target-schema.json`).
Ground truth for each is in `reference/expected-output/0X_<key>.json`.

---

## 15-minute demo talk-track

### 1. Set the scene (1 min)
Open Outlook (or any .eml viewer) and show the **6 broker emails** sitting in the underwriting intake mailbox.

> *"This is what an underwriter sees on a typical Monday morning. Six new submissions from six different brokers. Each has its own SOV template — different layout, different labels, different file format. Today this is hours of manual work. Let's see what Content Understanding does with it."*

Open one email — say `01_acme_submission.eml`. Point out:
- HTML signature with **broker logo as inline image** (slide 9 use case: "Producer info buried in image files")
- The SOV attached as `.xlsx`

### 2. Show the source-format chaos (2 min)
Open each attachment briefly:

| Open this | Point out |
|---|---|
| `01_acme_SOV.xlsx`  | Header block + schedule + **merged cells + hidden col + embedded image** with 3 extra locations |
| `02_cascade_SOV.xlsx` | Clean flat table — what the "ideal" world looks like |
| `03_magnolia_SOV.xlsx` | **4 worksheets** — Summary / Locations / CAT Exposure / Notes |
| `04_summit_SOV.pdf` | Native PDF with footnote markers next to specific locations |
| `05_heartland_SOV.pdf` | **Looks scanned** — slight skew, no selectable text |
| `06_coastal_SOV.xlsx` | Multi-row headers, **mid-table subtotal**, mixed USD + CAD, label drift across the file |

> *"Six brokers. Six layouts. Same business need. This is the '30+ template variations' problem you mentioned."*

### 3. The Content Understanding analyzer (4 min)
Switch to the **Insurance Workbench** (`apps/workshop/`, served at
<http://localhost:3000>) and open the **SOV Extraction** tab. Show:

- The **analyzer schema** matching `reference/target-schema.json` — one
  schema, all 6 templates target it. The "View / Edit" panel exposes the
  raw JSON so the audience sees schema-as-code.
- Pick **Acme** (the messy hero) → click Run.
- Walk through the output (left pane):
  - **Account-level fields** extracted from the header block (insured,
    effective date, broker, TIV) with confidence scores.
  - **Location rows** extracted from the schedule.
  - **3 extra locations** picked up from the **embedded image** — the
    rasterized TIFF preview on the right shows the embedded image was
    OCR'd as part of the page.
  - **Hover any Output row** to highlight its source polygon on the
    visualizer.
- Click **Validate** to show 100% match against ground truth (785/785
  in-source fields across the 4 xlsx samples).
- Click the **`est. $0.03`** pill in the header to show the cost
  breakdown: CU standard pages, contextualization tokens, GPT-4.1-mini
  token usage.

### 4. Fan-out across all 6 templates (3 min)
Run the remaining 5 SOVs through the **same** analyzer. Show side-by-side that:
- Cascade's flat table → same normalized JSON shape
- Magnolia's multi-sheet workbook → consolidated single output
- Summit's PDF → footnotes captured in `notes` field
- Heartland's scanned PDF → OCR + de-skew handled, margin annotation captured
- Coastal's messy spreadsheet → label drift normalized to canonical field names; CAD flagged

> *"One analyzer. Six templates. One schema. This is the 'hours to minutes' story from the deck."*

### 5. Validation, anomalies, risk scoring (3 min)
Switch to a downstream view (notebook / Power BI / simple UI) that consumes the normalized JSON. Demonstrate:

| Use case (slide 9–10) | What to show |
|---|---|
| **Valuation reasonability** | Acme Loc 18 + Cascade Loc 5 flagged as under-valued vs `benchmarks.csv` |
| **Flat / duplicated values** | Acme Locs 11–14 flagged ($5M placeholder) |
| **CAT clustering** | Magnolia: 9 of 15 locations in named-storm zone, ~62% of TIV |
| **High-hazard buried in list** | Summit Loc 8 — indoor firearms range → `shooting_involved: true` |
| **Currency normalization** | Coastal Loc 6 → `currency_mismatch` critical flag |
| **Risk scoring** | Top-5 ranked risk locations per account (drivers shown) |

### 6. The "AI vs Underwriter" closing slide (2 min)
Bring up slide 10 from the deck and walk through the boundary:

| Activity              | AI  | Underwriter |
|-----------------------|-----|-------------|
| Data extraction       | ✓   |             |
| Benchmarking          | ✓   |             |
| Risk flagging         | ✓   |             |
| Judgment & exceptions |     | ✓           |
| Appetite decisions    |     | ✓           |
| Relationship mgmt     |     | ✓           |

> *"The underwriter still owns judgment, appetite, and the broker relationship. Content Understanding clears the cognitive overhead so they can focus on the 5–10 locations that actually matter."*

---

## Mapping back to the deck

| Deck slide / use case                            | Where it shows up in this demo                                        |
|---------------------------------------------------|------------------------------------------------------------------------|
| Slide 7 — *Intelligent Ingestion & Normalization* | All 6 SOVs → one schema (`target-schema.json`)                         |
| Slide 7 — *Valuation Reasonability Checks*        | Acme Loc 18, Cascade Loc 5, Magnolia Loc 3, Acme Locs 11–14            |
| Slide 8 — *Risk Scoring & Prioritization*         | `derived_flags.top_risk_locations` in each expected-output JSON        |
| Slide 9 — *Over 30 template variations*           | Six radically different broker templates                                |
| Slide 9 — *"shooting" involved*                   | Summit Loc 8 (Colorado Springs indoor range)                           |
| Slide 9 — *Producer info buried in image files*   | Inline broker logo PNG in every email's HTML signature                 |
| Slide 9 — *Loss History/Run unstructured*         | Out of scope for this slot (Phase 4 stretch — see further considerations) |
| Slide 10 — *AI vs Underwriter boundary*           | Closing visual                                                          |
| Slide 11 — *Content Understanding framework*      | The studio walkthrough in step 3                                       |

---

## Disclaimer

All insured names, broker names, addresses, contact details, and financial figures in this demo are **entirely fictional** and used for workshop purposes only.
