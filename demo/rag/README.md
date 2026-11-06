# CU preprocessing and AI Search: three notebooks

The workflow follows the user's [Traditional_RAG](https://github.com/jomedinagomez/RAG_process/tree/main/Traditional_RAG)
examples, but the schema is designed for claim evidence rather than copied
from the reference. Each notebook is self-contained, uses the root `.venv`/`.env`, and
shows concise step summaries and compact previews. There are no app imports or `_lib.py`.

The workbench's **Claims Explorer** tab visualizes these actual folder/file/chunk
artifacts and can run the equivalent workflow through its own app service.
See the [app guide](../../apps/workshop/README.md#claims-explorer-workflow).
The notebooks remain self-contained; opening the app tab makes no paid calls.

## 1. Preprocess documents and display index-ready rows

[01_cu_extraction_step_by_step.ipynb](notebooks/01_cu_extraction_step_by_step.ipynb)
follows [preprocess_documents.ipynb](https://github.com/jomedinagomez/RAG_process/blob/main/Traditional_RAG/Preprocessing%20and%20Chunking/preprocess_documents.ipynb):

1. Preview the selected claim folder's files and show the total count.
2. Preview parsed emails and attachment/source links; summarize deduplication.
3. Review routes, then call native document/image analyzers for unique evidence.
4. Preview native Markdown, a figure and image summaries; save complete text.
5. Split document Markdown; preserve image summaries and citable figure rows.
6. Count tokens for the exact contextual embedding input.
7. Review title/section/evidence-kind/content together; no separate title vector.
8. Generate one content vector per row; show counts and dimensions only.
9. Preview metadata and deterministic IDs.
10. Preview the final `index_df`; retain every row and its full vector.
11. Check evidence completeness/provenance; save `processed-evidence-v1.json`.

It does **not** create an index, upload data or run chat. Native CU output is used
directly. Native figure descriptions have separate rows with exact figure IDs
and source regions, even when they overlap document Markdown. They are not
rewritten by a custom prompt.

### Document and image routing

- PDFs use `prebuilt-documentSearch`, including embedded photos/diagrams.
  Do not separately send PDF crops to CU.
- Standalone JPG/PNG photos and diagrams, including extracted email attachments,
  use `prebuilt-imageSearch`. Its native `fields.Summary.valueString` becomes
  searchable evidence; image results need not contain document Markdown.
- Review the routing cell before extraction. If an image file is actually a
  document scan, add its canonical filename to `document_image_names` so it uses
  document/OCR analysis. Unknown overrides fail rather than being ignored.
- The fixture's specifically named signature PNG remains excluded as branding;
  other inline/attached images are not indiscriminately dropped.

In the guided comparison for claim-001, documentSearch returned empty Markdown
and no figures for `damage-01.jpg`; imageSearch supplied a roof-damage description.
For `survey-chart.png`, imageSearch retained the three readings (12%, 18%, 36%)
and the chart's disclaimer that they do not establish causation or coverage.
These two samples justify the initial routing, not a general accuracy claim.
Further claims-specific customization should follow evidence-based evaluation.

Visual descriptions are observations, not proof of cause, timing, liability or
coverage. Claim context must not turn allegations into image-derived facts.
Keep conflicting accounts, estimates and proposals as distinct source evidence.

MSGs are parsed locally, including nested messages. Identical loose/attached
document bytes share one CU analysis while retaining source and parent links.
Saved raw results avoid repeat CU calls. Keys contain the actual analyzer, API
version and document hash, so image results cannot reuse document-analysis
results accidentally. Use a new output folder after changing cloud resources
or model configuration. No custom analyzers or resource defaults are created.

## 2. Create the index

[02_create_index.ipynb](notebooks/02_create_index.ipynb) follows
[Push_index/2_create_index.ipynb](https://github.com/jomedinagomez/RAG_process/blob/main/Traditional_RAG/Push_index/2_create_index.ipynb).
It previews the fields, prints vector/semantic configuration, and creates or
checks the index. It checks field types/attributes, vector profiles/algorithm
and semantic fields rather than accepting matching field names alone.
It does **not** call CU, generate embeddings or upload records.

## 3. Load the index and run semantic hybrid search

[03_populate_index.ipynb](notebooks/03_populate_index.ipynb) follows
[Push_index/3_populate_index.ipynb](https://github.com/jomedinagomez/RAG_process/blob/main/Traditional_RAG/Push_index/3_populate_index.ipynb).
It reads every row from `processed-evidence-v1.json`, validates vectors, identity
and evidence kinds, checks the target index before writing, and uploads with
batch summaries and previews any failures, then verifies selected-claim records.
Complete upload/deletion results are saved to JSON. Upload retries need not repeat
extraction or vectorization. After successful upload, stale chunks are removed
only for that claim; other claims are untouched.

After verification, **Step 5** follows the official
[semantic hybrid search sample](https://github.com/Azure/azure-search-vector-samples/blob/main/demo-python/code/basic-vector-workflow/azure-search-vector-python-sample.ipynb):

1. Embed the editable question with the same Foundry account, embedding
   deployment and dimensions used in notebook 1, through Entra ID.
2. Send `search_text` and a `VectorizedQuery` on `content_vector` together.
   Request 50 nearest-neighbor candidates and apply the `claim_id` prefilter.
3. Use `query_type='semantic'` and `semantic_configuration_name='claims-semantic'`
   to rerank the fused text/vector candidates, returning at most five results.
4. Preview filenames, evidence kinds, RRF/semantic scores and extractive captions.
   Full selected evidence stays in `hybrid_results`; vectors are not returned.

Unlike the sample's integrated vectorization, this push-based index uses a
client-generated question embedding; no Search vectorizer or new schema fields
are needed. A small selected claim can supply fewer than 50 candidates. Scores
are ranking signals, not probabilities; extractive captions are source excerpts,
not an LLM-generated answer or a claims determination.

The Search service must have **semantic ranker enabled**, in a supported
region/tier, as well as the index's `claims-semantic` configuration. Enablement
and usage limits are service-level prerequisites; these notebooks do not change
them. The query requests `semantic_error_mode='fail'` and checks reranker scores
so semantic failures do not silently become ordinary hybrid results.

When using a Foundry project's standard-agent setup, use the Search endpoint
from the project connection named in the `agents` capability host's
`vectorStoreConnections`, not an unrelated service found in the subscription.
Keep this demo's `claims-evidence-v1` index separate from agent-managed indexes.
The project URL identifies the project; CU, OpenAI and Search each use their
own service endpoint. No project connections or agent indexes are modified.

Edit and run the separate question cell in Step 5, then run the search cell
immediately below it. Setting the question makes no Azure calls; the search makes one
question-embedding call plus one Search request, not another CU/document
embedding run or upload. The query manages its own clients, so it remains
rerunnable even after the loading clients are closed by the final cleanup cell.

## Shared DataFrame/index columns

The final preprocessing DataFrame, index schema and loader use the same columns:

`id`, `claim_id`, `document_hash`, `chunk_id`, `title`, `header`, `content`,
`source_type`, `content_kind`, `filename`, `source_path`, `source_files`,
`parent_emails`, `figure_id`, `source_region`, `analyzer_id`,
`analyzer_api_version`, `content_vector`.

- `claim_id` scopes retrieval; `document_hash` groups chunks and exact duplicates.
- `source_type` is document, image or email. `content_kind` is document_text,
  image_description, figure_description or email_text. Image-format document
  scans can produce document_text while remaining image sources.
- `source_path` points to the local original or extracted attachment; a nested
  email points to its containing MSG. `source_files` preserves every original
  alias and nested attachment chain. These are local-demo paths, not hosted URLs.
- `source_region` retains native CU figure coordinates. No region is invented
  for an image summary. The analyzer API version is not a model-version claim.
- `chunk_id` is a positive integer local to a document; `id` is the deterministic
  claim/document/chunk hash.

One text embedding includes title, section, evidence kind and full content.
This is an embedding of visual descriptions, not an image-pixel embedding.
Native document summaries stay in raw CU results rather than being repeated on
every indexed chunk. Vector dimensions remain matched to the configured model;
vectors use `claims-content-profile` (HNSW/cosine) and are hidden from search
responses. `claims-semantic` prioritizes title, content and header.

For retrieval, combine keyword text, its query embedding on `content_vector`,
and semantic ranking, with an explicit `claim_id` filter for claim-scoped
questions. A claim filter is not authorization. Group cited evidence by its
document/source and retain the evidence kind when interpreting results.
Notebook 3 demonstrates this retrieval workflow after loading. It does not add
a chat or answer-generation workflow.

References are file-level; no separate page-number field is indexed.
Native figure IDs/regions remain available for visual evidence, and raw CU
results retain any native page information without adding it to the schema.

## Safe schema transition

Use a new index name such as `claims-evidence-v1`. If your existing `.env` still
sets `AZURE_SEARCH_INDEX_NAME=claims-cu-demo`, change that setting deliberately
before running notebook 2. Notebook defaults do not override an existing `.env`.
An incompatible index is rejected, never deleted, replaced or silently updated.

When changing Foundry accounts, restart the notebook kernels, select that
account's embedding deployment and use a new `CLAIMS_OUTPUT_ROOT`, for example
`output\claims\<account-name>`. Rerun notebook 1 there before loading: old raw
results and document vectors remain preserved under the previous output root
but must not be mixed into the new account's walkthrough.

The new versioned prepared-data filename leaves the old `processed.json`
untouched. Rerun notebook 1 for the new routes/contextual vectors, then create
the new index and load it with notebooks 2 and 3. Do not feed old two-vector
records into the new loader. Actual index creation and upload remain explicit
Azure-write cells; editing or local validation does not execute them.

## Compact teaching output

Record previews show at most **5 rows**, **160 characters per text cell** and
vector **dimensions only**. One native Markdown excerpt is limited to 1,200
characters, followed by one figure-description preview and short image-summary
previews. The 18-field index schema has a five-row preview and a field-name
summary; full CU payloads and repeated schema dumps are not printed.

These limits affect display only: `df`, `index_df`, saved CU results, native
Markdown and `processed-evidence-v1.json` retain complete values. Do not print entire vectors
or raw CU responses. Clearing notebook outputs does not delete these files or
restart the kernel. In an existing live kernel, run notebook 1's **Compact
display settings** cell once, without rerunning setup, CU or embeddings.

## Run together

Select the root `.venv` kernel. If a cell reports a missing dependency, install
only that named package in a visible terminal; do not reinstall all requirements.
Configure the existing root `.env` using [`.env.example`](../../.env.example):
CU endpoint/API, claim folder, output folder, Search endpoint/index, embedding
deployment and dimensions.

All three notebooks use **Microsoft Entra ID only**, through
`DefaultAzureCredential`; no API-key path is available. Embeddings reuse the CU
account and credential. The notebook converts the account's
`.cognitiveservices.azure.com` hostname to its `.openai.azure.com` hostname and
uses `/openai/v1/`. Both `.cognitiveservices.azure.com` and
`.services.ai.azure.com` CU hosts are supported. Set `AZURE_OPENAI_ENDPOINT`
to the verified same-account OpenAI endpoint if you prefer an explicit value;
otherwise it is derived from the CU host. No dated model API version is required.
The embedding deployment must exist in this same account.
The OpenAI SDK's `api_key` argument receives a renewable Entra token provider,
not an API key, following Microsoft's
[keyless v1 example](https://learn.microsoft.com/azure/foundry/openai/api-version-lifecycle).
Credentials are never printed.

For local development, `AZURE_TOKEN_CREDENTIALS=AzureCliCredential` can restrict
`DefaultAzureCredential` to the identity signed in through Azure CLI. The repo's
installed Azure Identity SDK supports this selection. Use it when VS Code,
broker or environment credentials select a different principal despite a
successful `az login`. Restart the notebook kernels after changing it so existing
credential objects are discarded. Keep this local-only; remove it when using a
deployed managed identity. Prefer the already-authorized identity over granting
new roles to an unexpected principal.

Original inputs stay under `data\claims\<claim_id>`. Ignored outputs are under
`output\claims`: shared `cu-results` and one folder per claim containing extracted
attachments, native Markdown/image summaries, `processed-evidence-v1.json`,
upload/deletion results.
Only the selected claim folder is ingested; root review aids are not inputs.

Run Azure steps deliberately in their visible cells. When correcting the
embedding-client configuration, rerun that cell and the embedding stages;
do not repeat CU extraction or chunking. Static syntax/structure checks do not
substitute for the guided Azure run.
