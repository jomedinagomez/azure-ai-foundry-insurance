# From Demo to Production — Closing Discussion

A working SOV extraction is a milestone, not a finish line. The next questions
are operational: *how much of this can we automate, what does it cost, where
does the data land, how do we keep it trustworthy, and who's done this
before?* This document covers the answers in the order we'll discuss them.

---

## 1. Routing decisions, not just extractions

The strategic question isn't "is the model right?" — it's "how do we use
confidence to decide where a human's time is best spent?"

### Measured today (4 SOV samples, zero-shot analyzer, 785 in-source fields)

| Confidence | Recommended action | Fields | % of total | Match accuracy |
| --- | --- | ---: | ---: | ---: |
| `> 0.95` | Auto-approve candidate | 24 | 3.1% | **100%** |
| `0.70 – 0.95` | Secondary review (sampling) | 676 | 86.1% | **100%** |
| `< 0.70` | Manual review (full) | 85 | 10.8% | **100%** |

**Headline: 785 in-source fields, zero mismatches.**

### What this means in practice

- These results are **zero-shot** — schema descriptions only, no labeled
  examples. This is the floor.
- The confidence model is **conservative**: even fields in the `< 0.70`
  bucket matched ground truth in this run. So today, confidence is best read
  as *"how much risk reduction does human review buy you?"* rather than a
  literal correctness signal.
- The lever you control: **labeled examples in Foundry Studio**. A small
  curated set of representative SOVs (with the correct values marked) lifts
  the `> 0.95` bucket substantially — moving more fields into the
  auto-approve lane and shrinking the manual-review tail.

> **The path forward:** *100% match in zero-shot is the floor. Pair this
> with labeled examples from your own submission backlog and the
> auto-approve bucket grows dramatically — that's how you move from
> "review-everything" to "review-the-exceptions."*

---

## 2. Who's done this before

### Featured story — Unum Group

**Case study:** [Unum Group builds custom AI application to search 1.3 TB of
data with 95% accuracy using Microsoft Azure generative AI](https://www.microsoft.com/en/customers/story/1772120481217819586-unumgroup-azure-insurance-en-united-states)

Unum Group — an international workplace-benefits insurer — used Azure AI
Search and Azure OpenAI to index 1.3 TB of unstructured policy contracts
(300,000 Word and PDF documents with complex grids), reducing
customer-query response time to **4–5 seconds with 95% accuracy at launch**.

### Why this story maps to Hanover

| Dimension | Unum | Hanover (SOV use case) |
| --- | --- | --- |
| Industry | Insurance | Insurance (commercial lines & specialty) |
| Document type | Policy contracts — PDFs / Word with complex grids | SOVs — xlsx / PDFs with location tables |
| Scale | 300,000 documents, 1.3 TB | Your submission backlog |
| Outcome | 4–5s retrieval, 95% accuracy | Pattern-match for confidence-based routing |
| Adoption | 90%+ of AskUnum employees in week one | Speaks to the human-in-the-loop story |

### Lessons that travel

- **PoC in two weeks; production in four months.** Unum stood up a working
  proof of concept on 100 policies in two weeks and deployed the full
  solution in four months.
- **Pre-trained models + iteration beats build-from-scratch.** Unum's CTO
  explicitly chose pretrained Azure models and refined through schema and
  prompt iteration — the same pattern we just demonstrated on your SOVs.
- **Three pillars Unum credits for success:** *"a deep understanding of the
  technology; clean, usable data; and a robust governance framework,
  including the incorporation of human oversight and responsibility."*

### Multi-document workflows

For where this evolves next — correlating the SOV with the broker email,
loss runs, and supporting financials — the Microsoft *Content Processing
Solution Accelerator* (V2) provides a DAG-based workflow engine for exactly
this kind of cross-document orchestration. We'll demo it earlier in the
session.

---

## 3. Where the extracted data lands

Extraction is the start of the value chain, not the end. The downstream
landing pattern matters as much as the model.

### Output shape

- **Structured JSON**, schema-versioned, with per-field provenance:
  - confidence score
  - source polygon on the input image
  - model version, schema version, run timestamp

### Integration patterns

| Pattern | Use case | Azure services |
| --- | --- | --- |
| **Event-driven** | Real-time submission triage | Azure Service Bus, Azure Event Grid |
| **Batch** | Nightly catch-up, historical re-processing | Azure Storage, Azure Data Factory |
| **API push** | Direct write to policy admin systems | Azure Functions / Logic Apps |

### Downstream systems we've integrated against

- **Guidewire PolicyCenter / ClaimCenter** (most common for commercial lines)
- **Duck Creek**
- Homegrown PAS / underwriting workbenches
- Data warehouses for portfolio analytics

### Schema versioning

Downstream contracts change. We treat the extraction schema as a versioned
artifact — older consumers continue to read v1 while new consumers opt into
v2 as they adapt.

---

## 4. Trustworthy at scale — security, residency, audit

Insurance data is regulated, and SOVs carry broker names, insured PII, and
sometimes financial detail. The platform is designed for this.

### Tenancy & residency

- **Customer-managed encryption keys (CMK)** on all storage and intermediate
  state.
- **VNet integration** and **private endpoints** — no traffic over the
  public internet.
- **Regional data residency** — the analyzer runs in the Azure region you
  choose; data does not leave it.
- **No training-data retention.** Microsoft does not use customer inputs to
  train or improve foundation models.

### Field-level audit

Every extracted field carries:

- **Source polygon** — the exact bounding box on the input page where the
  value came from.
- **Model version** — which underlying model produced this value.
- **Schema version** — which schema definition was active at extraction
  time.
- **Run timestamp** — when this extraction occurred.

This makes individual extractions **independently auditable** — a critical
property for regulated industries and for downstream dispute resolution.

### Identity & access

- **Microsoft Entra ID** integration; role-based access at the analyzer,
  pipeline, and result level.
- **Managed identity** for service-to-service auth — no secrets in code.

---

## 5. Cost narrative

A realistic operational view.

### Components

| Component | Driver | Notes |
| --- | --- | --- |
| **Content Understanding** | Per-page (analyzed) | Predictable, page-volume-driven. |
| **Azure OpenAI (GPT)** | Per token, in + out | Only consumed by `generate`-method fields (e.g., image fan-out, summarization). Most SOV fields use `extract` method — no GPT cost. |
| **Storage** | GB-month | Inbound documents, intermediate artifacts, output JSON. |
| **Compute** | Container Apps / Functions | Pipeline orchestration. Small relative to the above. |

### Demo run reference

For today's 4 SOV samples (22 + 8 + 15 + 6 = **51 locations across 4
multi-page workbooks**), the end-to-end CU cost was on the order of a small
number of dollars. We'll share the production-ready cost modeling in the
follow-up engagement based on your actual page volumes.

### Cost-control levers

- **Two-tier model selection** — use the smaller `gpt-4.1-mini` for routine
  generate-method fields; reserve the larger model for complex reasoning.
- **Caching at the analyzer level** — re-runs of identical inputs are free.
- **Confidence-driven fallback** — only invoke generate-method fallback for
  the fields that need it; don't pay LLM cost on `extract`-method fields.

---

## 6. Operations & lifecycle — Foundry as a developer platform

Today's demo included a real schema iteration: the source `Prepared By`
cell combined a name with a designation and a date. We adjusted the schema
description, redeployed the analyzer, and the next run picked up the change
cleanly. That's the everyday workflow — not a special event.

### How it stays maintainable

| Practice | What it looks like |
| --- | --- |
| **Schema as code** | Analyzer definitions live in git, reviewed via pull request. |
| **API-driven deployment** | `POST /analyzers/{template}/push` — automatable in CI/CD. |
| **Validation harness** | Re-run all known samples on every change; fail the build if accuracy drops. |
| **Regression detection** | Before promote-to-prod, diff current run against a golden set; surface field-level deltas. |
| **Observability** | Per-field confidence, latency, and version stamped on every run. |

### Why this matters

A document-extraction system you can't iterate on becomes a liability the
moment your document format changes. The lifecycle above makes the analyzer
a *living artifact* — owned by your team, evolved against real data,
governed like any other production service.

---

## Closing

Five themes for the conversation we'd like to have next:

1. **Sample diversity** — can we get 5–10 representative SOVs from your
   recent backlog to seed a labeled analyzer and lift the auto-approve
   bucket?
2. **Integration target** — which downstream system does the structured
   output need to land in first?
3. **Volume profile** — submissions per day, peak vs. average, typical page
   counts.
4. **Joint roadmap** — what's the right shape for the next engagement?
   Workshop continuation, focused PoC on real data, or partner-led
   implementation?
5. **Anything we missed** — what concerns haven't we addressed yet?
