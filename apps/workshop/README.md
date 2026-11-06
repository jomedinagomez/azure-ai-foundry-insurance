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
- **Claims Explorer** — folder gallery for all local claim packets, an
  evidence-processing timeline, original PDF/image/email pop-ups, attachment
  relationships, native extraction, and full-text chunk cards. Explicit run
  controls prepare one folder or all folders using the notebook workflow;
  optionally synchronize only those claims to the evidence Search index.
  The question view performs claim-filtered semantic hybrid retrieval.
  **System records** reviews the complementary synthetic claims ledger,
  activities and log notes through a separate local API tool.

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

Follow the [repository setup](../../README.md#3-clone-and-configure) to create
the root `.venv`, configure the root and web `.env` files, install dependencies,
and sign in to Azure. If the repository is already cloned, skip the clone and
`cd` commands. The `.venv` is shared by the API, notebooks, and audit scripts.
The API reads the root `.env` first; it uses `api/.env` only if the root file
is absent.

## Run the API and Web

Follow the [quick-launch instructions](../../README.md#4-run-the-insurance-workbench)
for the two terminal commands, a Node.js fallback, and the health check.
By default, the API serves on `http://localhost:8000` and the web app serves on
`http://localhost:3000`. The web app sends API requests to the URL in
`REACT_APP_API_BASE_URL`, set to `http://localhost:8000` in `web/.env.example`.
The analyzer list is available at `http://localhost:8000/analyzer-compare/analyzers`.

Open `http://localhost:3000`. Five tabs:

- **Analyzer Compare** — upload a doc, pick DI and CU analyzers (Layout is
  the default for both), run.
- **SOV Extraction** — pick a sample from `demo/sov/attachments/`, optionally
  override the pipeline (Auto resolves by file extension), click Run, then
  hover Output rows to highlight their bounding box on the right.
- **SEC Filings** — extract, inspect, validate, and export the five primary
  financial statements from the bundled filing.
- **Pipelines** — inspect / edit pipeline definitions.
- **Claims Explorer** — open `/#/claims`, choose a folder, and inspect its
  original files, native extraction and prepared chunks. File detail dialogs
  link attachments back to their emails. Use **Process this folder** or
  **Process all folders** to explicitly approve new CU/embedding usage; indexing
  is an additional opt-in in the confirmation dialog.

Analyzer Workshop has been retired from navigation, app rendering and backend
route registration. Old `/#/labeled-analyzer` links redirect to Claims Explorer;
the workbench no longer exposes `/labeled-analyzer/*` APIs. Historical source
helpers/assets are not purged by this change; their isolated router tests do
not register that retired router in the workbench.

### Claims Explorer workflow

The tab reads actual `data\claims\claim-*` inputs and the root
`CLAIMS_OUTPUT_ROOT` outputs. Existing notebook results appear immediately;
unprocessed folders remain clearly pending. It never uses the corpus review
notes as extraction or search input and does not fabricate completion states.

`api/app/services/claims_service.py` ports the self-contained notebooks'
native documentSearch/imageSearch routing, local nested MSG parsing,
exact-byte deduplication, Markdown sections, contextual embeddings and
18-field evidence contract. The notebooks remain independently runnable.
The browser receives full chunk text and vector dimensions, never vector
arrays. Native Markdown is rendered without raw HTML or remote image loads.

Image-format document scans can be marked for document/OCR analysis in a
single-folder run under **Advanced**. Each new confirmation starts with zero
overrides; photos and diagrams do not need to be selected there to be processed.
Bulk runs use the fixture default: PDFs to documentSearch,
photos/charts/diagrams to imageSearch. Inspect unusual images individually.
Visual observations do not establish cause, timing, liability or coverage.

Runs are serialized in this local single-process API. Progress is persisted
to `CLAIMS_OUTPUT_ROOT\app-run.json`; closing the tab does not cancel the
server job. If the API restarts, saved results remain and the interrupted job
is reported explicitly. Retry after fixing a failure to reuse cached CU
results and unchanged vectors from the configured account-specific output
root. Change the output root when changing accounts or embedding deployments.
Each open tab checks for new runs even while idle, so work started in another
tab replaces old status messages. Returning to a tab checks immediately.
Progress polling reconnects after a temporary
connection error; a failed saved run is labeled **Last run stopped**.
Local JSON writes and API reads share a process lock; files are written in
place because this Windows workspace does not permit replace-over-existing.
Do not run a notebook writer against the same output folder during an app run.

Indexing creates the named evidence index only if absent, validates an existing
schema rather than overwriting it, checks every upload, removes stale rows
only for the selected claim, and waits briefly for Search visibility.
The gallery's saved upload receipt is not a live check of remote index state.
Existing agent-managed indexes are untouched. **Ask this claim** makes one
query embedding and one semantic hybrid request, with source-linked results
rather than an LLM-generated answer.

The existing root `.env` supplies the Foundry and Search endpoints, deployment,
dimensions and Entra credential selection; see the
[RAG guide](../../demo/rag/README.md). Restart the API after changing `.env`.
These local endpoints have the same development-only trust model as the rest
of the workbench; do not expose the app publicly without authentication.

### Structured claims tool

`data/claims-operations/claims.json` adds a fixed, authored operational snapshot
for all six claim folders. Read-only `/claims-operations/claims` endpoints expose
claim summaries/snapshots, exact financials, activities and log notes. Folder IDs
and claim numbers are both accepted. Responses explicitly identify synthetic
local API data; they are not actual Databricks Genie responses.

The **System records** view reads this API separately from Search and links its
source references to existing evidence pop-ups. Posted/pending/voided payments,
outstanding reserve, contractor estimates and settlement approval remain distinct.
Due dates are evaluated against the snapshot, not today's clock.
See the [dataset and API contract](../../data/claims-operations/README.md).

**Ask this claim** remains the lightweight semantic hybrid retrieval view.
**Chat with claims**, available on the main gallery and inside a folder, adds
the local agent described below. These are separate experiences.

### Local claims agent and chat

The chat uses the existing backend process, the root `.venv`, and Entra ID.
Its conversation rail, central chat/citation cards and expandable trace blade
follow the local-custom-agent experience in `MicrosoftFoundryDemos`, without
copying that app's multi-agent/evaluation infrastructure.

1. Select **Chat with claims** on the gallery or a claim folder.
2. Select the conversation's claim. **Register agent** explicitly creates a
   Foundry **external-agent** version (currently a preview capability).
   It is observability metadata, not hosted compute or a new Azure resource
   deployment. The registered name/version are saved; rendering chat never
   creates a version.
3. Choose **New conversation**, then ask about the selected claim. The model
   runs a bounded function-calling loop with two read-only tools:
   - `search_claim_evidence`: existing claim-filtered semantic hybrid Search.
   - `get_structured_claim`: HTTP GET to the actual local
     `/claims-operations/claims/{claim_id}` API, not an in-agent fixture shortcut.
4. Inspect the returned source IDs/cards and **Show trace** for actual model
   calls, tool arguments/results, measured timings and reported token counts.
   No hidden model reasoning is exposed. Source excerpts are untrusted data,
   not instructions.
5. **Verify cloud trace** queries the project's Application Insights for the
   saved trace ID. The exact KQL and observed rows are shown. Flushing telemetry
   alone is not proof of ingestion; the UI reports that distinction.

The claim is bound server-side; tool schemas cannot override it. Use a new
conversation to switch claims. Conversation state and actual turns are stored
in `CLAIMS_OUTPUT_ROOT\agent\conversations.sqlite3`. Failed turns retain their
errors/tool evidence, never a success-shaped assistant answer. An API restart
marks an interrupted turn as failed. Closing the chat does not cancel a server
invocation; reopen the conversation to inspect its saved state.

The demo limits a turn to six tool calls/seven model responses and a conversation
to 30 turns. The most recent six successful turns supply conversational context;
their prior source references are retained. Configuration/prompt/tool changes
invalidate the saved registration; register a new version and start a new
conversation. Registration and chat are explicit cloud operations.

Configuration: `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_SUBSCRIPTION_ID`,
`AZURE_RESOURCE_GROUP`, `CLAIMS_AGENT_NAME`, `CLAIMS_AGENT_MODEL_DEPLOYMENT`
(defaults to `APP_CU_COMPLETION_DEPLOYMENT`), and
`CLAIMS_STRUCTURED_API_BASE_URL` (loopback only; default `http://127.0.0.1:8000`).
The agent discovers the existing selected project's App Insights connection
through ARM metadata; it never creates another monitoring resource or displays
its connection string. Export authentication uses Entra ID. Actual synthetic
conversation/tool contents are recorded for this tracing demonstration; review
telemetry/content-retention requirements before using non-demo data.
Provider size limits can truncate cloud attributes; the local turn record keeps
the tool results shown by the UI.

Foundry registration requires access to the project and its standard-agent
dependencies, including Cosmos DB. Network/firewall errors remain explicit:
the app never changes service networking, RBAC or billing automatically.
Live network changes to the development group must be reconciled with its
owning Terraform before the next apply; public endpoints do not disable auth.

Current dependencies include the Foundry project SDK and OpenAI 3.x, plus
Azure Monitor and the pinned compatible GenAI instrumentation helper. The
notebooks' OpenAI v1 embedding call shape is unchanged. For debugging, use
**Claims local agent API (.venv)** in the root VS Code launch configuration;
stop the existing API task before starting a debugger on the same port.

This is a local-only demo, not an authorization boundary or a deployment
template. The model cannot approve coverage, pay or settle a claim, change
activities, or write operational records. Genie data is explicitly synthetic.

### Horizontal execution tree

Open a claim folder and choose **Execution tree**. This additional, read-only
pop-up preserves the existing gallery and file/chunk views. It uses the app's
existing ReactFlow dependency; no new rendering service is needed.

- Expand a file's path to follow **approach → native output → chunks →
  contextual embeddings → Search**. Unfold a chunk group to see each actual
  prepared chunk as its own branch.
- Email attachments branch from their parent message, including forwarded MSGs.
  A loose file that also occurs as an attachment stays a single evidence node,
  with a dashed shared-copy relationship rather than duplicate processing.
- Focus on one file to retain its provenance ancestors and child attachments
  while hiding unrelated evidence. Pan, zoom, use the minimap or **Fit tree**.
- Open original/native/chunk nodes in the existing detail views; **Back to
  execution tree** retains expansion, focus and viewport.
- Approach, vector and Search nodes expose recorded execution details.
  **Saved artifact** is distinct from an observed run completion or cache hit.
  Only known file-scoped failures are attributed to a file; otherwise the
  failure remains a folder-level message.

The chronology panel shows only the existing retained run log (up to 200
events), in its stored order. Event numbers describe that retained window,
not an invented full-history sequence. Timestamps/durations were not recorded
by the current pipeline and are not inferred from files or stage positions.
Saved output views are not a replay, and saved upload receipts are not live
Search-health checks. The tree opens without paid calls or backend restarts.

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
| Web: `npm` not recognized | Node.js/npm not on PATH | Use the [Node.js fallback](../../README.md#4-run-the-insurance-workbench) or install Node.js with npm |
| Web: calls fail with mixed-port URL | Web `.env` not loaded by CRA | Check `REACT_APP_API_BASE_URL` in `web/.env`, then restart the web server |
| API: `APP_CONTENT_UNDERSTANDING_ENDPOINT` missing | API configuration is missing or incomplete | Configure the repository-root `.env`, or `api/.env` if no root `.env` exists |

## Notes

- No MSAL — auth flows from the developer's `az login` via
  `DefaultAzureCredential`. Set `APP_ENV=dev` (already the default in
  `.env.example`) to keep that behavior.
- The standalone API trims out the accelerator's Cosmos / ServiceBus /
  App Configuration paths. If you need those later, copy from
  `content-processing-solution-accelerator/src/ContentProcessorAPI/app/`.
