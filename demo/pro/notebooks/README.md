# Pro Mode notebooks

Walk through the Azure Content Understanding pro-mode preview end-to-end.

| # | Notebook | What it does |
|---|---|---|
| 01 | `01_deploy_pro_analyzers.ipynb` | Register `proClaimsV1` + `proFraudV1` with `auto_policy.pdf` as reference data. |
| 02 | `02_analyze_claim.ipynb` | Multi-input reasoning over the clean `claim_auto_collision` package. |
| 03 | `03_detect_fraud.ipynb` | CU reasoning + rule engine over the tampered `claim_auto_collision_fraud` package; blended 0–100 risk score. |
| 04 | `04_end_to_end.ipynb` | Deploy + iterate every sample for smoke-testing. |

## Setup

1. Run the data pipeline once:
   ```powershell
   python demo/pro/scripts/make_all.py
   ```
2. In the repo-root `.env`, set:
   - `APP_CONTENT_UNDERSTANDING_ENDPOINT=https://<your-foundry>.cognitiveservices.azure.com/`
   - `APP_ENV=dev` (uses `DefaultAzureCredential` / `az login`).
3. `az login` if you haven't already.
4. Use the same Python interpreter the workshop API uses — the notebook helper `_lib.py` adds `apps/workshop/api/` to `sys.path` so notebooks and the API share one implementation.

## Pro-mode caveats

- Preview API only: `2025-05-01-preview`. Pinned in `pro_service.API_VERSION`.
- Documents only (PDF / images supported). No audio, no video inputs.
- No confidence scores, no grounding. The fraud demo compensates with `fraud_rules.py`.
- Reference data is fetched in *lookup mode* — keep it small and focused (one policy).
- Field methods are `classify` + `generate` only (no `extract`).
- Region availability varies. Use `/pro/healthcheck` to probe at runtime.

See the [MS Learn Standard vs Pro modes article](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/standard-pro-modes).
