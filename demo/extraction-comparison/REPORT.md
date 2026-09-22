# ClaimForm_1 extraction comparison report

- **Validated:** September 21, 2026
- **Input:** `data/propertyclaims/ClaimForm_1.pdf`
- **Pages:** 2
- **Azure region:** West US
- **Content Understanding analyzer setup:** 3.768 seconds, excluded from per-document latency

## Executive summary

| Measure | Document Intelligence + Query Fields | Content Understanding |
| --- | ---: | ---: |
| Reviewed fields matched | 14/14 | 14/14 |
| Extraction latency | 6.656 s | 6.877 s |
| Separate Azure AI Language PII latency | 1.326 s | 0.970 s |
| End-to-end latency | 7.982 s | 7.848 s |
| Estimated retail cost without PII | $0.040000 | $0.027455 |
| Estimated retail cost with PII | $0.043000 | $0.031455 |

## Conclusion

Both approaches matched all 14 reviewed fields on this clean synthetic property
claim. Content Understanding had an approximately 26.8% lower estimated retail
cost including PII and a similar end-to-end latency in this one run. Document
Intelligence completed extraction slightly faster and uses a GA API with a more
deterministic processing model. Content Understanding offers a richer schema and
greater semantic flexibility, but adds contextualization/model billing,
deployment quota dependencies, and a preview API.

For stable claim forms like this one, Document Intelligence remains the simpler
operational choice. For highly variable or semantically complex claim documents,
Content Understanding is worth testing across a representative corpus. This
single clean form is not enough to select a production architecture.

PII is a separate Azure AI Language stage in both paths. Neither extraction
service should be assumed to redact sensitive data before embeddings or indexing.

## Field-by-field results

| Field | Expected | Document Intelligence | DI confidence | Content Understanding | CU confidence |
| --- | --- | --- | ---: | --- | ---: |
| PolicyholderFirstName | Sophia | Sophia | 0.993 | Sophia | 0.984 |
| PolicyholderLastName | Kim | Kim | 0.995 | Kim | 0.988 |
| TelephoneNumber | 646-555-0789 | 646-555-0789 | 0.995 | 646-555-0789 | 0.978 |
| PolicyNumber | PH5678901 | PH5678901 | 0.995 | PH5678901 | 0.989 |
| CoverageType | Homeowners | Homeowners | 0.995 | Homeowners | 0.991 |
| ClaimNumber | CLM5432109 | CLM5432109 | 0.995 | CLM5432109 | 0.978 |
| PolicyEffectiveDate | 2022-07-01 | 2022-07-01 | 0.995 | 2022-07-01 | 0.986 |
| PolicyExpirationDate | 2023-07-01 | 2023-07-01 | 0.995 | 2023-07-01 | 0.990 |
| DamageDeductibleAmount | 1000 | $1,000 | 0.995 | 1000 | 0.928 |
| DateOfDamageOrLoss | 2023-05-10 | 2023-05-10 | 0.995 | 2023-05-10 | 0.984 |
| TimeOfLoss | 13:20 | 13:20 | 0.995 | 13:20:00 | 0.994 |
| DatePrepared | 2023-05-11 | 2023-05-11 | 0.994 | 2023-05-11 | 0.977 |
| PropertyAddress | 3344 Birch St, New York, NY 10001 | 3344 Birch St, New York, NY 10001 | 0.995 | 3344 Birch St, New York, NY 10001 | 0.930 |
| MailingAddress | 3344 Birch St, New York, NY 10001 | 3344 Birch St, New York, NY 10001 | 0.995 | 3344 Birch St, New York, NY 10001 | 0.929 |

Currency and time values were normalized before exact-match scoring.

## Latency

| Approach | Stage | Seconds |
| --- | --- | ---: |
| Document Intelligence | Layout + Query Fields | 6.656 |
| Content Understanding | Content + field extraction | 6.877 |
| Document Intelligence | Azure AI Language PII | 1.326 |
| Content Understanding | Azure AI Language PII | 0.970 |
| Document Intelligence | End to end | 7.982 |
| Content Understanding | End to end | 7.848 |

These values are from one execution and do not represent p50, p95, or p99
latency.

## PII stage

| Approach | Extracted characters | Billable 1,000-character records | Detected entities | Seconds |
| --- | ---: | ---: | ---: | ---: |
| Document Intelligence text | 2,394 | 3 | 30 | 1.326 |
| Content Understanding text | 3,059 | 4 | 29 | 0.970 |

Entity count is not an accuracy measure. The redacted output needs a reviewed PII
test set to measure false negatives and false positives.

## Pricing components

The estimate uses West US public retail rates and the measured CU usage response.

| Approach | Component | Quantity | Rate | Estimated USD |
| --- | --- | ---: | ---: | ---: |
| Document Intelligence | S0 prebuilt/layout pages | 2 pages | $10/1K | $0.020000 |
| Document Intelligence | Query Fields add-on | 2 pages | $10/1K | $0.020000 |
| Document Intelligence | Azure AI Language PII | 3 text records | $1/1K | $0.003000 |
| Content Understanding | Standard document extraction | 2 pages | $5/1K | $0.010000 |
| Content Understanding | Standard contextualization | 2,000 tokens | $0.001/1K | $0.002000 |
| Content Understanding | GPT-5.2 global input | 5,697 tokens | $1.75/1M | $0.009970 |
| Content Understanding | GPT-5.2 global cached input | 5,504 tokens | $0.175/1M | $0.000963 |
| Content Understanding | GPT-5.2 global output | 323 tokens | $14/1M | $0.004522 |
| Content Understanding | Azure AI Language PII | 4 text records | $1/1K | $0.004000 |

The estimate excludes embeddings for downstream Search, Azure AI Search search
units, storage, Service Bus, Functions, retries, reprocessing, discounts, and
commitment tiers.

## Rate limits and throughput

| Service | Published admission limit | Relevant payload limit |
| --- | --- | --- |
| Document Intelligence S0 | 15 analyze POST/s; 50 result GET/s | 500 MB; 2,000 pages |
| Content Understanding S0 | 1,000 pages/images/min; 3,000 operations/min | Async: 200 MB and 300 pages |
| Azure AI Language PII S | 1,000 requests/s and 1,000 requests/min | Sync: 5 documents/request; 5,120 chars/document |
| Azure AI Search push API | Batch API limits apply | 1,000 documents or 16 MB/request |

For this two-page claim:

| Constraint | Approximate documents/minute |
| --- | ---: |
| DI submission quota | 900 |
| CU page quota | 500 |
| PII request quota | 1,000 |
| Observed DI single-worker latency | 9.01 |
| Observed CU single-worker latency | 8.72 |

Content Understanding is also constrained by the linked Foundry model deployment
TPM. Admission limits are not completion-throughput guarantees.

No HTTP 429 responses occurred. Document Intelligence returned a five-second
`Retry-After` polling interval, which the SDK honored.

## Content Understanding measured usage

```json
{
  "documentPagesStandard": 2,
  "contextualizationTokens": 2000,
  "tokens": {
    "gpt-5.2-input": 5697,
    "gpt-5.2-cached-input": 5504,
    "gpt-5.2-output": 323
  }
}
```

## Downstream index-size scenario

Assumptions: 2,000-character chunks, 200-character overlap, 3,072-dimensional
float32 embeddings, 1.3 HNSW scenario multiplier, and one million source
documents.

| Approach | Characters | Chunks/document | Raw vector bytes/document | Scenario bytes/document | Projected corpus GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Document Intelligence | 2,394 | 2 | 24,576 | 34,342 | 31.98 |
| Content Understanding | 3,059 | 2 | 24,576 | 35,007 | 32.60 |

This excludes filterable fields, ACL metadata, other Search structures, replicas,
and blue/green indexes. Validate actual capacity with Azure AI Search service and
index statistics.

## Decision criteria still requiring a larger corpus

- Printed, scanned, and handwritten claim variants
- Field precision/recall and confidence calibration
- PII false-negative and false-positive rates
- Warm p50, p95, and p99 latency
- Backfill throughput under quota and throttling
- Human-review rate
- Reprocessing cost after schema or model changes
- Search storage and retrieval quality
