# Notebooks — run in order

| # | Notebook | What it does |
| --- | --- | --- |
| 01 | [01_upload_training_data.ipynb](01_upload_training_data.ipynb) | Create/reuse a storage account + container and upload `invoice/` and `claim/` prefixes. |
| 02 | [02_train_classifier.ipynb](02_train_classifier.ipynb) | Prepare Layout sidecars, build the classifier with a short-lived container SAS, and inspect the model. |
| 03 | [03_classify_from_storage.ipynb](03_classify_from_storage.ipynb) | Classify documents that live in Blob Storage, via a short-lived per-blob SAS URL. |
| 04 | [04_classify_local_file.ipynb](04_classify_local_file.ipynb) | Classify individual local files (bytes) — drop in your own file. Optional accuracy + confidence eval. |

Shared setup lives in [_lib.py](_lib.py): endpoint/credential resolution, client
construction, blob upload, Layout-sidecar preparation, SAS minting, and result
formatting.

See the [demo README](../README.md) for prerequisites, the auth model, and the
Content Understanding vs. Document Intelligence comparison.

## Notes

- **Auth:** `DefaultAzureCredential` (run `az login`) unless `DOCUMENTINTELLIGENCE_KEY`
  is set. The signed-in identity needs **Cognitive Services User** on the Foundry
  resource and **Storage Blob Data Contributor** on the storage account.
- **Endpoint:** notebooks reuse `FOUNDRY_ENDPOINT`. If that is the
  `*.services.ai.azure.com` form, set `DOCUMENTINTELLIGENCE_ENDPOINT` to the
  `*.cognitiveservices.azure.com` form in `.env` (or `_lib.py` derives it from
  `FOUNDRY_RESOURCE_NAME`).
- **Splitting:** the notebooks use `split='none'` (one class per file). Use
  `split='auto'` for files that concatenate multiple documents.
