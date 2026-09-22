# Insurance Workbench

Local-only workshop shell branded **Insurance Workbench**. Five tabs share one
FastAPI + React stack:

- **Analyzer Compare** — side-by-side Azure Document Intelligence vs. Azure
  AI Content Understanding on the same file. Defaults to `prebuilt-layout`
  for both. Each result pane shows an estimated-cost pill (with breakdown
  popover) that uses the real `usage` block returned by CU and DI's
  per-1,000-pages rate.
- **SOV Extraction** — end-to-end SOV pipeline: sample picker, pipeline
  dropdown, live-progress dialog, validation against ground truth. The
  right pane is a draggable resizable visualizer with:
  - **pdf.js**-based PDF viewer (zoom/pan/page-nav, no browser-download
    bypass needed)
  - **TIFF viewer** with `react-zoom-pan-pinch` zoom/pan + multi-page nav +
    SVG **field-bounding-box overlays**, hover-driven from the Output pane
  - Returned **markdown** + raw **artifacts** sub-tabs
- **SEC Filings** — two-stage Content Understanding extraction of the five
  primary consolidated financial statements from a 10-K / 10-Q. One CU
  call (classifier delegates to analyzer via `contentCategories.analyzerId`)
  produces multi-segment output; the service merges, exports a multi-sheet
  Excel workbook, and validates against ground truth. Companion notebooks
  live in [`demo/sec/notebooks/`](../../demo/sec/notebooks/README.md) and
  call the same `sec_service` functions the UI uses.
- **Pipelines** — visual DAG editor for the seeded pipelines (PDF extract,
  xlsx generate, xlsx generate + image fan-out, xlsx via PDF→TIFF). SSE
  streaming for per-step progress events.
- **Analyzer Workshop** — create a forms project, upload local training and
  evaluation PDFs, auto-label with a named analyzer or label manually from OCR,
  review one document at a time, export labeled triplets, build a learned
  GPT-5.2 analyzer, and compare it against the zero-shot analyzer. Customers do
  not need Content Understanding Studio or storage credentials; optional model
  training uses temporary storage managed by the API host.

Every SOV run carries a `meta.cost` breakdown computed from CU's `usage`
block: per-tier page counts (minimal/basic/standard) × the published
per-1,000-pages rate, plus contextualization tokens, plus per-model LLM
token rates. Source: <https://learn.microsoft.com/azure/ai-services/content-understanding/pricing-explainer>.

## Layout

```
apps/workshop/
├── web/      React (CRA + Fluent UI + react-pdf + react-zoom-pan-pinch)
└── api/      FastAPI standalone backend (no Cosmos / ServiceBus / AppConfig)
```

## Prerequisites

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) (`winget install astral-sh.uv`)
- Node.js 18+
- Azure CLI signed in: `az login`
- An Azure AI Foundry (or Cognitive Services) endpoint with both
  Document Intelligence and Content Understanding available
- Foundry model deployments named `gpt-5.2`, `gpt-4.1-mini`, and
  `text-embedding-3-large`. The SOV analyzer templates declare
  `"models": { "completion": "gpt-4.1-mini" }`. Re-run
  [`demo/sov/scripts/ab_model_compare.py`](../../demo/sov/scripts/ab_model_compare.py)
  before changing the model.
- **LibreOffice** on PATH if you want to run the `xlsx_via_pdf_tiff` pipeline
  (Windows: `winget install TheDocumentFoundation.LibreOffice`)
- Your signed-in identity needs `Cognitive Services User` (or stronger) on
  the Foundry resource

## One-time setup (from repo root)

```powershell
cd <repo-root>
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
```

This creates a single `.venv/` at the repo root used by every Python entry
point in the repo (workshop API, SOV notebooks, audit scripts).

## Run the API

```powershell
cd apps/workshop/api
copy .env.example .env
# Edit .env: set APP_CONTENT_UNDERSTANDING_ENDPOINT to your Foundry/Cognitive Services endpoint
az login
..\..\..\.venv\Scripts\Activate.ps1
python standalone_api.py
```

API serves on `http://localhost:8000`. Smoke test:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/analyzer-compare/analyzers
```

## Run the Web

In a second terminal:

```powershell
cd apps/workshop/web
npm install
copy .env.example .env
npm start
```

Web serves on `http://localhost:3000` and proxies API calls to
`REACT_APP_API_BASE_URL` (default `http://localhost:8000`).

Open `http://localhost:3000`. Five tabs:

- **Analyzer Compare** — upload a doc, pick DI and CU analyzers (Layout is
  the default for both), run.
- **SOV Extraction** — pick a sample from `demo/sov/attachments/`, optionally
  override the pipeline (Auto resolves by file extension), click Run, then
  hover Output rows to highlight their bounding box on the right.
- **SEC Filings** — extract, inspect, validate, and export the five primary
  financial statements from the bundled filing.
- **Pipelines** — inspect / edit pipeline definitions.
- **Analyzer Workshop** — create a project, add training/evaluation PDFs,
  prepare or auto-label each document, review and export labels, then build and
  score the learned analyzer.

Each result has an `est. $0.0X` pill in the header — click it for the
per-component breakdown.

## Cost configuration

Per-unit pricing lives in
[`api/app/services/pricing.json`](api/app/services/pricing.json). Tune any
row to match your enterprise agreement; the cost engine reloads via API
restart (`reload_pricing()` is available for tests). The CU rates default
to the public pay-as-you-go prices (CU: $5/1k standard pages, $1/1k basic,
$0.01/1k minimal; DI: $10/1k for prebuilt models, $1.50/1k for Read).

## Adding a new tab

Future features (e.g. SOV extraction, insurance) follow the same pattern:

**API** — add a router under `api/app/routers/<feature>.py` and register it
in `standalone_api.py`:

```python
from app.routers import analyzer_compare, my_feature
app.include_router(my_feature.router)
```

**Web** — add:
- `web/src/Pages/<Feature>Page.tsx`
- A route entry in `web/src/App.tsx`
- A tab entry in `web/src/Components/Header/Header.tsx`
- A service module under `web/src/services/<feature>Service.ts`

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| API: `401` from analyzer call | Not signed in / wrong tenant | `az login --tenant <tenant>` |
| API: `403` from analyzer call | Missing data-plane RBAC | Grant `Cognitive Services User` on the endpoint resource |
| Web: dropdowns empty | API not running or CORS blocked | Confirm `http://localhost:8000/health` returns 200 |
| Web: calls fail with mixed-port URL | `.env` not loaded by CRA | Restart `npm start` after editing `.env` |
| API: `APP_CONTENT_UNDERSTANDING_ENDPOINT` missing | `.env` not created | `copy .env.example .env` and edit |

## Notes

- No MSAL — auth flows from the developer's `az login` via
  `DefaultAzureCredential`. Set `APP_ENV=dev` (already the default in
  `.env.example`) to keep that behavior.
- The standalone API trims out the accelerator's Cosmos / ServiceBus /
  App Configuration paths. If you need those later, copy from
  `content-processing-solution-accelerator/src/ContentProcessorAPI/app/`.
