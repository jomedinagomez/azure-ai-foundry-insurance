# SEC Extraction — Notebooks

These notebooks document the **exact** code paths used by the workshop's
SEC Filings UI. Each notebook imports from
`apps/workshop/api/app/services/sec_service.py` (via `_lib.py`), so there
is **one** implementation shared between the API, the UI, and the
workshop — no parallel snippets to keep in sync.

## Setup

```powershell
# from repo root
.\.venv\Scripts\Activate.ps1
# (optional) make sure .env has APP_CONTENT_UNDERSTANDING_ENDPOINT set
jupyter lab demo/sec/notebooks
```

## Parity map

| Notebook | UI feature | Service function | Step event |
| --- | --- | --- | --- |
| [01_deploy_analyzers](01_deploy_analyzers.ipynb) | (implicit on first run) | `sec_service.ensure_analyzers()` | `deploy_analyzers` |
| [02_classify_pdf](02_classify_pdf.ipynb) | "Run extraction" — classifier stage | `sec_service.classify_and_extract()` | `cu_classify_and_extract` |
| [03_analyze_segments](03_analyze_segments.ipynb) | retry badge / per-segment counts | `sec_service.classify_and_extract(max_retries=…)`, `_has_empty_tables()` | `cu_classify_and_extract` |
| [04_merge_and_export](04_merge_and_export.ipynb) | Statement tabs + **Download Excel** | `sec_service.merge_segments()`, `sec_service.export_to_excel()`, `sec_excel.load_from_payload()` | `merge_segments`, `excel_export` |
| [05_validate](05_validate.ipynb) | Validation panel | `sec_service.validate()` | (none — runs after `complete`) |
| [06_end_to_end](06_end_to_end.ipynb) | the **Run extraction** button, soup to nuts | `sec_service.run_extraction()` | all of the above |

## Anti-drift convention

Every notebook starts with:

```python
from _lib import sec_service, sec_excel
```

If you find yourself copy-pasting CU client code into a notebook, stop —
add the helper to `sec_service.py` instead and call it from the notebook.
That way the UI, the API, and the workshop never diverge.

## Caching

Notebooks 04–06 prefer cached classifier output from
`demo/sec/reference/cu-output/<stem>_v2_classified.json` to keep runs
fast and offline-friendly. To force a fresh Azure call, pass
`use_cache=False` or delete the cache file.
