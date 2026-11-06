
# Azure AI Foundry – Insurance Content Understanding

> SOV-first. Built for underwriting. Designed to scale to claims and beyond.

Already set up? [Launch the Insurance Workbench](#4-run-the-insurance-workbench).

## Overview

This repository provides a **reference implementation and workshop materials** for applying **Azure AI Foundry** to insurance document workflows.

The initial focus is on **Statement of Values (SOV) processing** for **Commercial Lines (CL) & Specialty underwriting**, with extensibility to **claims, loss runs, and multi-document scenarios**.

---

## Business Context – Statement of Values (SOV)

A **Statement of Values (SOV)** is a **semi-structured document** representing insured assets at the location level and serves as the **primary exposure document** for underwriting.

### Characteristics
- Delivered as **Excel, PDF, or broker-generated formats**
- Contains **critical exposure and valuation data**
- Exhibits **high variability across submissions**

### Typical fields
- Location / address
- Construction, occupancy, year built
- Square footage
- Replacement cost values (Building, Contents, BI)
- CAT indicators (flood, seismic, coastal)

---

## How Underwriters Use the SOV

Underwriters rely on the SOV to:

- Assess **exposure distribution**
- Evaluate **Total Insured Value (TIV)**
- Identify **risk concentration and accumulation**

This drives:
- Coverage structure (limits, deductibles, sublimits)
- Risk selection and appetite decisions
- Identification of underwriting exceptions

---

## Problem Statement

The current SOV workflow presents several challenges:

- Manual review of large documents
- Inconsistent formats and field naming
- Repetitive data extraction and re-keying
- Limited validation and benchmarking
- Hidden risks within dense datasets

**Impact:**
- Slower quote turnaround
- Increased underwriting risk
- Reduced scalability
- Lower underwriter efficiency

---

## Target Use Case – SOV Automation

### Intelligent Ingestion & Normalization
- Extract data from **Excel, PDF, and mixed formats**
- Normalize fields into a **standard schema**
- Detect **missing or malformed values**

### Automated Validation
- Perform **reasonability checks**
- Compare values against benchmarks
- Flag inconsistencies and anomalies

### Risk Scoring & Prioritization
- Generate **location-level risk scores**
- Rank exposures by importance
- Highlight critical underwriting focus areas

---

## End-to-End Scenario (Workshop Alignment)

The solution is structured around a **real-world underwriting workflow**:

1. Submission intake (email / broker submission)
2. SOV ingestion (Excel / PDF)
3. Data extraction
4. Field normalization
5. Validation & anomaly detection
6. Risk evaluation and prioritization
7. Underwriter decisioning

The **CL & Specialty walkthrough** (led by the customer) is expected to demonstrate:
- Current process flow
- Existing systems and tooling
- Key bottlenecks and manual steps

---

## Complexity of the Use Case

This scenario is complex due to:

### Input variability
- 30+ template variations
- Inconsistent labeling (e.g., TIV vs Total vs Bldg)

### Semi-structured + unstructured data
- Excel, PDF, and embedded content
- Free-text annotations and broker notes

### Semantic interpretation
- Mapping business concepts to standardized schemas
- Identifying relevant vs irrelevant signals

### Multi-document workflows
- SOV + loss runs + claims + emails
- Cross-document reasoning requirements

### Human-in-the-loop requirement
- AI supports extraction and validation
- Underwriters retain judgment and final decisions

---

## Solution Approach – Azure AI Foundry

Core components:

- **Content Understanding**
  - Document ingestion, extraction, classification
  - Per-field source grounding and confidence scoring
- **Custom analyzers & schemas**
  - Field-level mapping and normalization (`sovExtractV1`, `sovGenerateV1`)
- **Post-processing logic**
  - Confidence scoring, tolerant validation against ground truth, schema-as-code lifecycle
- **Integration layer**
  - APIs into underwriting systems (e.g., Pega, Guidewire)

### What's in this repo

| Asset | Purpose |
|---|---|
| [`apps/workshop/`](apps/workshop/) | **Insurance Workbench** — local FastAPI + React app: Analyzer Compare, SOV Extraction, SEC Filings, Pipelines, and **Claims Explorer** for evidence visualization, structured records, semantic hybrid retrieval and a local two-tool agent chat with verified Foundry traces. |
| [`demo/sov/`](demo/sov/) | Six synthetic broker submissions (4 xlsx + 2 PDF) covering 30+ template variations, plus generators, ground-truth, and benchmarks. |
| [`demo/sov/notebooks/`](demo/sov/notebooks/) | End-to-end extraction methodology, four input shapes (PDF / Excel / Excel+images / xlsx-via-TIFF), and tolerant validator. |
| [`demo/sec/`](demo/sec/) | Five real SEC 10-K / 10-Q PDFs, classifier+analyzer templates, cached CU outputs, and ground-truth expected line-items. |
| [`demo/sec/notebooks/`](demo/sec/notebooks/README.md) | Six notebooks (`01_deploy_analyzers` → `06_end_to_end`) that call the **same** `sec_service` functions the SEC Filings tab uses — no drift between UI and workshop. |
| [`demo/content-understanding/`](demo/content-understanding/README.md) | Reused official Microsoft multimodal notebooks: PDF, receipt image, audio, video/keyframes, field extraction and classification; pinned upstream sources and MIT attribution included. |
| [`demo/architecture/`](demo/architecture/) | Current local claims architecture and proposed Azure-hosted agent + Databricks Genie architecture, with editable diagrams and slide previews. |
| [`data/claims-operations/`](data/claims-operations/README.md) | Six authored synthetic operational claim records and a local read-only API-tool contract for assignment, financials, activities and claim log notes. |
| [`demo/handwritten/`](demo/handwritten/) | Self-contained field-extraction notebook comparing GPT-5.2 handwriting judgments with Document Intelligence's native handwriting signal. |
| [`demo/classifier/`](demo/classifier/) | Document Intelligence custom classifier for invoice-vs-claim routing, with local and Blob inference examples. |
| [`demo/sov/preprocess/`](demo/sov/preprocess/) | Reusable client primitives: page-setup preflight, LibreOffice render, TIFF rasterization. |
| [`demo/sov/reference/analyzer-templates/`](demo/sov/reference/analyzer-templates/) | The two analyzer JSON templates (extract + generate). Schema-as-code; pushed via API. |
| [`demo/sov/scripts/`](demo/sov/scripts/) | Validation harness (`review_xlsx.py`), model A/B (`ab_model_compare.py`), confidence-bucket analysis (`confidence_buckets.py`), token-cost audit (`inspect_token_cost.py`). |

### Where we landed today

| Metric | Value |
|---|---|
| **Accuracy** | 100% (785/785 in-source fields across 4 xlsx samples) |
| **Cost per SOV (gpt-4.1-mini)** | $0.03 – $0.05 typical |
| **Cost vs. gpt-4.1** | ~70% cheaper, same accuracy (validated A/B) |
| **Default analyzer model** | `gpt-4.1-mini` |
| **Default DI/CU compare analyzers** | `prebuilt-layout` (both) |

---

## Extensibility – Beyond SOV

While this implementation focuses on **SOV**, the same architecture extends to:

### Claims processing
- Claim number extraction and validation
- Document classification (legal, medical, inquiry)
- Summarization of claim-related documents

### Loss runs
- Extraction of claim history and loss amounts
- Aggregation across documents

### Email / broker ingestion
- Extract structured data from email bodies and attachments

---

## Workshop Context

This repository aligns with a **solutioning workshop**:

- Introduction and objectives
- Azure AI Foundry overview
- Demo (Content Understanding + analyzers)
- Architecture patterns
- Customer walkthrough (end-to-end flow)
- SOV demo aligned to workflow
- Q&A and next steps

---

## Inputs Required

To execute the scenario effectively:

- Sample SOV documents (Excel/PDF)
- Priority data fields (e.g., TIV, BPP, totals)
- Business rules for validation
- Representative end-to-end workflow

---

## Repository Structure

```
azure-ai-foundry-insurance/
├── apps/workshop/                   # Insurance Workbench (local app)
│   ├── api/                         # FastAPI backend (standalone, no Cosmos/ServiceBus)
│   └── web/                         # React + Fluent UI + pdf.js visualizer
├── demo/sov/                        # Six synthetic SOV submissions + ground truth
│   ├── attachments/                 # The 6 SOVs (xlsx + pdf)
│   ├── emails/                      # Six broker .eml files
│   ├── notebooks/                   # Methodology + four extraction approaches
│   ├── preprocess/                  # Shared client primitives (preflight, render, rasterize)
│   ├── reference/                   # Analyzer templates, target schema, ground-truth, benchmarks
│   └── scripts/                     # Generators + validation/A-B harnesses
├── requirements.txt                 # Unified Python deps (workshop API + notebooks)
└── .env.example                     # Repo-root env template (shared by API + notebooks)
```

---

## Getting started

### 1. Prerequisites

| Tool | Version | Install (Windows) |
|---|---|---|
| Python | 3.12 | <https://www.python.org/downloads/> |
| `uv` | latest | `winget install astral-sh.uv` |
| Node.js | 18 LTS or newer | `winget install OpenJS.NodeJS.LTS` |
| Azure CLI | latest | `winget install Microsoft.AzureCLI` |
| LibreOffice *(optional)* | latest | `winget install TheDocumentFoundation.LibreOffice` — only needed for the `xlsx_via_pdf_tiff` pipeline |

### 2. Azure prerequisites

- An **Azure AI Foundry** (or Cognitive Services multi-service) resource with **Content Understanding** and **Document Intelligence** available in its region.
- A model deployment named **`gpt-4.1-mini`** on that Foundry resource (and **`text-embedding-3-large`** if you exercise the default analyzers). The SOV analyzer templates declare `"models": { "completion": "gpt-4.1-mini" }`.
- Your signed-in identity (the user running `az login`) must hold **`Cognitive Services User`** on the Foundry / Cognitive Services resource. The app and notebooks authenticate via `DefaultAzureCredential` — no keys are used or stored.

### 3. Clone and configure

```powershell
git clone https://github.com/jomedinagomez/azure-ai-foundry-insurance.git
cd azure-ai-foundry-insurance

# Create a single venv at the repo root, used by the API and the notebooks
uv venv --python 3.12 .venv
uv pip install -r requirements.txt

# Repo-root .env — picked up by both the API and the notebooks
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Edit .env and set:
#   APP_CONTENT_UNDERSTANDING_ENDPOINT=https://<your-foundry-or-cognitive-services-endpoint>/
#   APP_ENV=dev

# Install web dependencies and create its configuration once
Set-Location apps\workshop\web
npm install
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
Set-Location ..\..\..

az login
```

### 4. Run the Insurance Workbench

Open two VS Code PowerShell terminals at the repository root. These steps assume
the `.venv`, web dependencies, and `.env` files were configured in step 3.
There is no need to reinstall dependencies or copy `.env` files on each launch.

**Terminal 1 — API:**

```powershell
Set-Location apps\workshop\api
& '..\..\..\.venv\Scripts\python.exe' 'standalone_api.py'
```

**Terminal 2 — Web:**

```powershell
Set-Location apps\workshop\web
npm start
```

If `npm` is not on PATH but Microsoft Scout is installed, run the following
instead of `npm start` in the web terminal. This uses Scout's bundled Node.js
and requires the web dependencies to have already been installed:

```powershell
$nodeDir = Join-Path $env:LOCALAPPDATA 'Programs\Microsoft Scout\resources\node'
$env:PATH = "$nodeDir;$env:PATH"
$env:BROWSER = 'none'
& "$nodeDir\node.exe" '.\node_modules\react-scripts\bin\react-scripts.js' start
```

If that Node.js executable is unavailable, install Node.js with npm as listed
in the prerequisites and reopen the terminal. If the web dependencies have not
been installed, complete that part of step 3 before running `npm start`.

Once the web server finishes compiling, open <http://localhost:3000>. Check the
API at <http://localhost:8000/health>; it should return `{"message":"I'm alive!"}`.
The health check confirms the API is running, not that Azure authentication is
valid. Run `az login` if an Azure-backed operation needs a new session.

Keep both terminals open while using the app. Press **Ctrl+C** in each terminal
to stop it. If a port is already in use, check whether the app is already running.

Five tabs are available: **Analyzer Compare**, **SOV Extraction**, **SEC Filings**,
**Pipelines**, and **Claims Explorer**. See [`apps/workshop/README.md`](apps/workshop/README.md)
for per-tab details, cost-pill behavior, and troubleshooting.

### 5. Run the SOV extraction notebooks

```powershell
.\.venv\Scripts\Activate.ps1
code demo\sov\notebooks\01_extract_sov.ipynb
```

In VS Code, select the `.venv` kernel when prompted. The notebooks read `APP_CONTENT_UNDERSTANDING_ENDPOINT` from the **repo-root `.env`**. Run cells top-to-bottom; outputs are cached under `demo/sov/reference/cu-output/`.

See [`demo/sov/notebooks/README.md`](demo/sov/notebooks/README.md) for the four extraction approaches, schema-as-code lifecycle, and the tolerant validator.

### 6. (Optional) Verify reproducibility

Run [`demo/sov/notebooks/03_validate_extraction.ipynb`](demo/sov/notebooks/03_validate_extraction.ipynb) end-to-end against the cached extractions in `demo/sov/reference/cu-output/`. Expected result: **100% accuracy on in-source fields** for all 4 xlsx samples.

Optional deeper audits (require the API from step 4 to be running, since they hit `http://localhost:8000`):

```powershell
# Per-sample cost + token usage + accuracy against ground truth
python demo\sov\scripts\ab_model_compare.py

# Where LLM-input tokens go for one cached run (schema vs OCR text)
python demo\sov\scripts\inspect_token_cost.py
```

## test

---

## Disclaimer

This repository is provided as a **sample reference implementation** for demonstration and workshop purposes.

- Not production-ready
- Should be adapted to meet security, compliance, and operational requirements
- Intended for guidance and experimentation

---

## License

This project is licensed under the MIT License.