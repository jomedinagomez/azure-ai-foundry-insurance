
# Azure AI Foundry – Insurance Content Understanding

> SOV-first. Built for underwriting. Designed to scale to claims and beyond.

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
| [`apps/workshop/`](apps/workshop/) | **Insurance Workbench** — local FastAPI + React app: Analyzer Compare, SOV Extraction with interactive PDF/TIFF visualizer and field-overlay highlighting, Pipelines DAG view, per-run **cost breakdown** popover. |
| [`demo/sov/`](demo/sov/) | Six synthetic broker submissions (4 xlsx + 2 PDF) covering 30+ template variations, plus generators, ground-truth, and benchmarks. |
| [`demo/sov/notebooks/`](demo/sov/notebooks/) | End-to-end extraction methodology, four input shapes (PDF / Excel / Excel+images / xlsx-via-TIFF), and tolerant validator. |
| [`demo/sov/preprocess/`](demo/sov/preprocess/) | Reusable client primitives: page-setup preflight, LibreOffice render, TIFF rasterization. |
| [`demo/sov/reference/analyzer-templates/`](demo/sov/reference/analyzer-templates/) | The two analyzer JSON templates (extract + generate). Schema-as-code; pushed via API. |
| [`demo/sov/scripts/`](demo/sov/scripts/) | Validation harness (`review_xlsx.py`), model A/B (`ab_model_compare.py`), confidence-bucket analysis (`confidence_buckets.py`), token-cost audit (`inspect_token_cost.py`). |
| [`slidedecks/`](slidedecks/) | Customer-facing deck content (Azure CU pitch, multi-modal accelerator overview, SOV demo closing notes). |

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
│   ├── api/                         # FastAPI + Pydantic backend
│   └── web/                         # React + Fluent UI + pdf.js visualizer
├── demo/sov/                        # Six synthetic SOV submissions + ground truth
│   ├── attachments/                 # The 6 SOVs (xlsx + pdf)
│   ├── emails/                      # Six broker .eml files
│   ├── notebooks/                   # Methodology + four extraction approaches
│   ├── preprocess/                  # Shared client primitives (preflight, render, rasterize)
│   ├── reference/                   # Analyzer templates, target schema, ground-truth, benchmarks
│   └── scripts/                     # Generators + validation/A-B harnesses
├── Docs/                            # Customer-provided scoping artifacts
├── slidedecks/                      # Microsoft-prepared decks + closing notes
└── feedback/                        # Research notebooks documenting trade-offs and gotchas
```

## Getting started

```powershell
# One-time setup (Python deps shared across notebooks + workbench API)
uv venv --python 3.12 .venv
uv pip install -r requirements.txt

# Backend
cd apps/workshop/api
copy .env.example .env   # set APP_CONTENT_UNDERSTANDING_ENDPOINT
az login
python standalone_api.py

# Frontend (second terminal)
cd apps/workshop/web
npm install
copy .env.example .env
npm start
```

App at <http://localhost:3000>, API at <http://localhost:8000>.

See [`apps/workshop/README.md`](apps/workshop/README.md) for app-specific details and
[`demo/sov/notebooks/README.md`](demo/sov/notebooks/README.md) for extraction methodology.

---

## Disclaimer

This repository is provided as a **sample reference implementation** for demonstration and workshop purposes.

- Not production-ready
- Should be adapted to meet security, compliance, and operational requirements
- Intended for guidance and experimentation

---

## License

This project is licensed under the MIT License.