# Claim extraction comparison

This demo compares two schema-based extraction approaches against the same
synthetic property claim and reviewed expected values:

1. **Azure AI Document Intelligence** `prebuilt-layout` with the Query Fields
   add-on.
2. **Azure Content Understanding** with a custom field schema.

The notebook also measures Azure AI Language PII as an explicit, separate stage.
Neither extraction approach should be assumed to remove PII automatically.

The consolidated result from the verified `ClaimForm_1.pdf` run is in
[`REPORT.md`](REPORT.md). A live notebook run overwrites that report and also
writes timestamp-independent Markdown and JSON snapshots under the ignored
`output/` directory.

## Run

1. Install the repository requirements into the root `.venv`.
2. Populate the repository-root `.env`.
3. Select `.venv\Scripts\python.exe` as the notebook kernel.
4. Open
   [`notebooks/01_compare_claim_extraction.ipynb`](notebooks/01_compare_claim_extraction.ipynb).
5. Set `EXTRACTION_COMPARISON_RUN_AZURE=true` in `.env` when you are ready to
   incur service charges. Set `EXTRACTION_COMPARISON_RUN_PII=true` to include the
   separate PII stage.

The default input is
[`data/propertyclaims/ClaimForm_1.pdf`](../../data/propertyclaims/ClaimForm_1.pdf).
The notebook doesn't install packages and refuses to run outside the repository
`.venv`.

## Environment

Existing repository variables are reused:

- `APP_CONTENT_UNDERSTANDING_ENDPOINT`, `CONTENTUNDERSTANDING_ENDPOINT`, or
  `FOUNDRY_ENDPOINT`
- `FOUNDRY_RESOURCE_NAME` to derive the
  `*.cognitiveservices.azure.com` endpoint
- `GPT52_MODEL_DEPLOYMENT`
- `EMBEDDING_MODEL_DEPLOYMENT`
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, and `AZURE_TENANT_ID`, or another
  `DefaultAzureCredential` source

Optional comparison variables:

- `DOCUMENTINTELLIGENCE_ENDPOINT`
- `LANGUAGE_ENDPOINT`
- `EXTRACTION_COMPARISON_RUN_AZURE` (default `false`)
- `EXTRACTION_COMPARISON_RUN_PII` (default `false`)
- `EXTRACTION_COMPARISON_CONFIGURE_DEFAULTS` (default `true`)
- `EXTRACTION_COMPARISON_ANALYZER_ID`
- `EXTRACTION_COMPARISON_LANGUAGE_TIER` (`S`, `Multi-service`, `S0`, or `F0`)
- `EXTRACTION_COMPARISON_CORPUS_DOCUMENTS`
- `AZURE_PRICING_REGION` (default `eastus`)
- `DI_LAYOUT_METER`, `DI_QUERY_FIELDS_METER`, and `LANGUAGE_PII_METER`
- `CU_MODEL_INPUT_METER`, `CU_MODEL_CACHED_INPUT_METER`, and
  `CU_MODEL_OUTPUT_METER`
- `CU_INPUT_TOKENS_INCLUDE_CACHED` (default `false`; enable only if your usage
  contract reports cached input as a subset of the input count)

API keys are supported through `CONTENTUNDERSTANDING_KEY`,
`DOCUMENTINTELLIGENCE_KEY`, `LANGUAGE_KEY`, or `FOUNDRY_KEY`, but Microsoft
Entra authentication is preferred.

## What the notebook measures

- Extraction coverage and normalized exact-match accuracy for 14 reviewed fields
- Content Understanding field confidence and source-grounding configuration
- Document Intelligence, Content Understanding, and optional PII latency
- Observed request IDs, throttling headers, and `Retry-After` values
- Published admission, payload, and batching limits
- Current regional retail rates fetched from the Azure Retail Prices API
- Component-level estimated cost per document
- Search chunk count and raw-vector/index-size scenarios

Retail rates are public list prices, not negotiated or commitment-tier prices.
Always verify the selected meter names, region, deployment type, and bill before
making a production decision. A single run is useful for validation, not for
p50/p95 latency; repeat the benchmark on a representative corpus.

## Validation snapshot

One live validation run on September 21, 2026 used `ClaimForm_1.pdf` in West US.
Content Understanding analyzer setup took 3.77 seconds and is excluded from
per-document latency.

| Measure | Document Intelligence + Query Fields | Content Understanding |
| --- | ---: | ---: |
| Reviewed fields matched | 14/14 | 14/14 |
| Extraction latency | 6.66 s | 6.88 s |
| Separate PII latency | 1.33 s | 0.97 s |
| End-to-end latency | 7.98 s | 7.85 s |
| Estimated list cost without PII | $0.0400 | $0.0275 |
| Estimated list cost with PII | $0.0430 | $0.0315 |

The CU estimate used the response's actual usage: two standard document pages,
2,000 contextualization tokens, 5,697 input tokens, 5,504 separately reported
cached-input tokens, and 323 output tokens. Cached tokens were priced using the
cached-input meter. The estimates exclude downstream embeddings, Search,
storage, orchestration, retries, discounts, and commitment pricing.

This clean synthetic form is not representative enough for a product decision.
The same notebook should be run against handwriting, scans, document variants,
and production-like batches to establish p50/p95/p99 latency and quality.

## Official references

- [Content Understanding pricing](https://learn.microsoft.com/azure/ai-services/content-understanding/pricing-explainer)
- [Content Understanding limits](https://learn.microsoft.com/azure/ai-services/content-understanding/service-limits)
- [Document Intelligence limits](https://learn.microsoft.com/azure/ai-services/document-intelligence/service-limits)
- [Document Intelligence Query Fields](https://learn.microsoft.com/azure/ai-services/document-intelligence/concept/query-fields)
- [Azure AI Language limits](https://learn.microsoft.com/azure/ai-services/language-service/concepts/data-limits)
- [Azure AI Search limits](https://learn.microsoft.com/azure/search/search-limits-quotas-capacity)
