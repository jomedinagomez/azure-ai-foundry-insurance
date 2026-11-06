# Synthetic claims operations tool

[claims.json](claims.json) is an authored, fixed **2026-11-05 18:00 UTC**
snapshot for the six fictional [claim evidence folders](../claims/).
Every identity, assignment, payment, activity and log note is fictional.
There is no customer data, real Databricks connection or source-file generator.

The customer workflow calls for three complementary sources: documents,
structured claim records and semi-structured claim log notes. This fixture
simulates the latter two; the original documents remain on the existing
Content Understanding / AI Search path. The file is intentionally outside
`data/claims/claim-*`, so processing a claim folder cannot index it as evidence.

## What is new, and what stays unresolved

The operational records add assignment/team, workflow phase, financial ledger,
blocking activities, due dates and dated log notes. Policy identifiers, specimen
limits/deductibles, insured names, loss dates and reserve totals are consistent
with the existing fictional corpus. New operational events do not retrospectively
prove document allegations, cause, ownership, warning-sign timing or coverage.

| Claim | Reference | Specimen policy | Outstanding reserve | Posted payments |
|---|---|---|---:|---:|
| claim-001 | AV-26-004181 | AV-CP-260101 | USD 25,000.00 | USD 375.00 expense |
| claim-002 | AV-26-004267 | AV-CP-260207 | USD 42,000.00 | USD 620.00 expense |
| claim-003 | AV-26-004318 | AV-CV-260319 | USD 9,500.00 | USD 180.00 expense |
| claim-004 | AV-26-004401 | AV-GL-260406 | USD 18,000.00 | None |
| claim-005 | AV-26-004459 | AV-CP-260512 | USD 12,000.00 | USD 225.00 expense |
| claim-006 | AV-26-004507 | AV-CP-260618 | USD 68,000.00 | USD 1,100.00 expense |

All six claims remain open with coverage under review and no approved settlement
amount. Null approval is not a zero-dollar settlement. An inspection expense
does not imply repair authorization or acceptance of coverage.

Important preserved distinctions:

- Claim 001's reported incident-time discrepancy is unresolved; maintenance and
  cause evidence remain outstanding.
- Claim 002's concealed equipment condition is not established by photographs.
  A diagnostic request and scope reconciliation remain open.
- Claim 003's later USD 7,420.00 correspondence is not a replacement estimate PDF
  or a payment. A pending sensor allowance is not a completed sensor test.
- Claim 004's later sign photo does not establish its earlier position. The
  cleaning-log gap and conflicting accounts remain unresolved.
- Claim 005's missing-item count is not reconciled by exterior lock photographs.
- Claim 006's USD 48,600.00 original inspection, USD 52,400.00 later email-only
  proposal, USD 68,000.00 reserve and USD 1,100.00 posted expenses are different
  measures. The proposed controls addition still lacks diagnostic support.

## Local API tool

Start the existing workshop API with the root `.venv`. The read-only contract is
available in [the local Swagger UI](http://localhost:8000/docs#/claims-operations):

| Operation | Endpoint |
|---|---|
| List summaries, optionally filter status/line of business | `GET /claims-operations/claims` |
| Full claim snapshot | `GET /claims-operations/claims/{claim_reference}` |
| Ledger and exact totals | `GET /claims-operations/claims/{claim_reference}/financials` |
| Activities, optionally filter status/current blockers | `GET /claims-operations/claims/{claim_reference}/activities` |
| Newest notes first, bounded by `limit` (1-50) | `GET /claims-operations/claims/{claim_reference}/log-notes` |

Use either `claim-006` or `AV-26-004507` as the claim reference. Unknown claims
return 404, invalid query values return 422, and an unavailable/invalid dataset
fails explicitly rather than returning an empty healthy-looking result.
There are no write, arbitrary SQL or free-text natural-language-query endpoints.

Every response has `metadata` (synthetic marker, fixed as-of time, source-system
label, implementation and caveat) and `data`. OpenAPI operation IDs provide the
future function-tool contract, including `get_structured_claim_snapshot`.

This simulates **the read-only data-tool boundary**, not Databricks Genie's actual
API/MCP wire protocol, natural-language-to-SQL behavior, latency or authorization.
A later local agent can call this HTTP API as one tool and semantic hybrid
Search as the other. It must not pretend that this fixture is a live lakehouse.

## Financial and temporal semantics

- All amounts are nonnegative USD decimals, serialized as **strings**, with
  exact `Decimal` arithmetic on the server.
- Outstanding reserve = indemnity reserve + expense reserve.
- Paid = **posted** indemnity + posted expense payments only.
- Pending requests and requests voided before posting are excluded from paid.
- Incurred = outstanding reserve + paid, before recoveries. It is not a
  settlement formula; deductibles/limits are not automatically applied.
- Across the fixture: outstanding reserve USD 174,500.00, posted paid
  USD 2,500.00, incurred USD 177,000.00, pending requests USD 2,250.00 and
  voided requests USD 200.00.
- Activity overdue/blocking flags are computed against the fixed snapshot date,
  not the machine's current date. Completed activities are never current blockers.
- Notes retain stable IDs, recorded timestamps, author roles and activity links.
  Evidence references must resolve inside that same claim's folder.

## Review in Claims Explorer

Open a folder and choose **System records**. Inspect the assignment, specimen
policy, exact financial summary, activities, payment ledger and log notes.
Evidence-link buttons open the existing source-file dialogs. **Open tool response**
shows the actual JSON response. Refreshing this view makes local GET requests,
not model or Search calls.

The [Claims Explorer chat](../../apps/workshop/README.md#local-claims-agent-and-chat)
now consumes this API as a real loopback HTTP tool alongside semantic hybrid
Search. It registers the local runtime as a Foundry external agent for telemetry,
retains actual model/tool evidence and separately verifies cloud trace ingestion.
This fixture itself makes no model or telemetry calls.
