# Document Intelligence — Custom Classifier (invoice vs. claim)

Train an **Azure AI Document Intelligence custom classification model** (v4.0 GA,
API `2024-11-30`) to tell **invoices** apart from **property-claim forms**, then
classify documents two ways:

1. **From a storage account** — documents that live in Azure Blob Storage.
2. **From individual local files** — bytes uploaded straight from disk.

Unlike the Content Understanding classifier, the Document Intelligence classifier
returns a **confidence score per document type**, so you can threshold and route
(auto-accept / human review) directly off the response.

## Why Document Intelligence (not Content Understanding) here?

| | Content Understanding classifier | Document Intelligence custom classifier |
| --- | --- | --- |
| Confidence per class | ❌ not returned | ✅ `confidence` (0–1) per `docType` |
| Training | zero-shot from category descriptions | supervised from labeled sample files |
| Training data source | — | **Azure Blob Storage only** |
| Min samples | — | **2 classes, 5 samples per class** |

## Classes and data

| Class | Source folder | Files |
| --- | --- | --- |
| `invoice` | [`data/invoices/`](../../data/invoices) | 5 PDFs |
| `claim` | [`data/propertyclaims/`](../../data/propertyclaims) | 8 PDFs |

> Invoices are exactly at the 5-sample minimum, so **all five are used for
> training** and there is no held-out invoice for a clean test. The classify
> notebooks reuse the training files (and the handwritten claim) for
> demonstration. For a real accuracy measurement, add a few more invoice PDFs.

## Prerequisites

1. An existing **Foundry AIServices resource** (this repo's `infra/non-private`).
   Its endpoint exposes the Document Intelligence classifier API. `az login` with an
   identity that has **Cognitive Services User** on that resource.
2. An **Azure Storage account**. Notebook `01` reuses `STORAGE_ACCOUNT_NAME` if set,
   otherwise creates one (needs `az` CLI + rights to create the account and a role
   assignment).
3. Python deps from the repo-root [`requirements.txt`](../../requirements.txt)
   (`azure-ai-documentintelligence`, `azure-storage-blob`, `azure-identity`).
4. `demo/classifier/.env` copied from [`.env.example`](.env.example).

## Auth model

- **Training** uses a short-lived **user-delegation container SAS** with `rwdl`
  permissions, as shown in the [custom classifier documentation](https://learn.microsoft.com/azure/ai-services/document-intelligence/train/custom-classifier?view=doc-intel-4.0.0).
  Notebook `02` also creates the raw Layout API `.ocr.json` sidecar required for
  every source document before it submits the build.
- **Classify-from-URL** cannot use that managed identity for the input document, so
  notebook `03` mints a short-lived **user-delegation SAS** for the specific blob.
- **Classify-from-file** sends bytes directly — no storage involved.

## Run order

| Notebook | Purpose |
| --- | --- |
| [`01_upload_training_data.ipynb`](notebooks/01_upload_training_data.ipynb) | Create/reuse storage and upload `invoice/` + `claim/` prefixes |
| [`02_train_classifier.ipynb`](notebooks/02_train_classifier.ipynb) | Prepare Layout sidecars, build the classifier with a container SAS, inspect result |
| [`03_classify_from_storage.ipynb`](notebooks/03_classify_from_storage.ipynb) | Classify a blob via a per-blob SAS URL |
| [`04_classify_local_file.ipynb`](notebooks/04_classify_local_file.ipynb) | Classify an individual local file (bytes); drop in your own file |

Shared setup (clients, endpoint/credential resolution, paths, blob upload,
result formatting) lives in [`notebooks/_lib.py`](notebooks/_lib.py).
