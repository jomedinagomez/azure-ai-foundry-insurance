# Pro Mode demo — Claims & Fraud Detection

Showcases **Azure Content Understanding pro mode** (preview API `2025-05-01-preview`):
multi-step reasoning across multiple input documents, with a reference dataset
(policy) baked into the analyzer at deploy time.

Two scenarios — one per use case:

| Scenario | Folder | Use case |
|---|---|---|
| `claim_auto_collision` | `samples/claim_auto_collision/` | Clean claim package — multi-document reasoning |
| `claim_auto_collision_fraud` | `samples/claim_auto_collision_fraud/` | Tampered estimate — blended fraud detection |

Inputs are **realistic synthetic PDFs generated locally** (no curated JSON). The damage photograph is the one published file we don’t generate — it’s fetched verbatim from the
[Microsoft Content Processing Solution Accelerator v2](https://github.com/microsoft/content-processing-solution-accelerator)
`claim_date_of_loss/` bundle, and the other generated documents (FNOL,
police report, estimate) describe damage consistent with that image.

- `reference-data/auto_policy.pdf` — synthetic auto policy (declarations + conditions + exclusions).
- `source-data/generated/claim_form.pdf` — FNOL claim form (Contoso Casualty).
- `source-data/generated/police_report.pdf` — Springfield PD traffic crash report.
- `source-data/generated/repair_estimate.pdf` — clean body-shop estimate (under sub-limit, post-loss date, matching VIN).
- `source-data/generated/damage_photo.png` — fetched from CPSA v2 by `scripts/fetch_damage_photo.py`.
- The fraud variant’s `samples/claim_auto_collision_fraud/repair_estimate.pdf` is a freshly-rendered tampered estimate (inflated total, pre-loss date, VIN typo).

Generators run with `reportlab`.

## Quick start

```powershell
# From repo root
python demo/pro/scripts/make_all.py    # generates every input PDF + PNG and stages both samples
```

Then run the notebooks in `notebooks/` (`01` → `04`) or hit the workshop API:

```
POST /pro/samples/claim_auto_collision/analyze
POST /pro/samples/claim_auto_collision_fraud/analyze
```

## Pro mode caveats

- **Preview API** — `2025-05-01-preview`. Pinned in `pro_service.py`.
- **Documents only** — pro mode does not support video, audio, or images
  as inputs. The `damage_photo.png` is sent as image-mode reference.
- **No confidence scores, no grounding** — the fraud demo compensates with
  a small rule engine (`apps/workshop/api/app/services/fraud_rules.py`).
- **Reference data** is fetched in *lookup mode* at analysis time; keep it
  small and focused (one policy PDF, not the whole library).
- **Field methods** — only `classify` and `generate` (no `extract`).
- **Region availability** — varies. The `/pro/healthcheck` endpoint probes
  the configured Foundry resource at runtime.

See [MS Learn — Standard and pro modes](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/standard-pro-modes)
for the official reference.
