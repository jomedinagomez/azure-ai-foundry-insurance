# Scanned PDF preprocessing for Content Understanding

The incoming document is always a **scanned PDF**. Content Understanding remains the extraction service. These examples test whether preprocessing the same scan changes the results returned by the **same configured CU analyzer**.

The supplied local PDF is already scanned; no replacement document is needed. There is no intake-image requirement, separate OCR engine or source-image-extraction step.

## Start with notebook 02

| Notebook | Comparison |
|---|---|
| [02 - Original scan versus rendered scan](notebooks/02_render_pdf_to_tiff.ipynb) | Original scanned PDF to CU versus the same pages rendered at 300 dpi and sent to the same CU analyzer. |
| [03 - Optional filters](notebooks/03_test_denoising_and_sharpening.ipynb) | Apply optional denoising/sharpening to renders of that scanned PDF, then send each version to the same analyzer. |
| [04 - Compare CU results](notebooks/04_compare_results.ipynb) | Show returned structured fields separately from Markdown amount/sign checks, with screenshots and saved responses. |

**Notebook 01 is not required and is not part of this workflow.** Each of the three notebooks above is self-contained and reads its input from the local `.env`; there are no shared helper scripts or dependencies on another kernel's variables.

PDFium renders pages, Pillow/OpenCV optionally filter them, and **CU performs extraction**. TIFF is simply the supported transport format for a preprocessed scan. No Tesseract, EasyOCR, direct language-model calls or AI upscaling are used.

## Setup

Use the repository's Python 3.12 environment. From the repository root:

```powershell
uv pip install --python .venv\Scripts\python.exe -r demo\ocr\requirements.txt
Copy-Item demo\ocr\.env.example demo\ocr\.env
az login
```

Do not overwrite an existing local `.env`. Select the repository `.venv` kernel and set the notebook working directory to `notebooks/`.

| Local `.env` setting | Purpose |
|---|---|
| `OCR_INPUT_FILE` | Scanned PDF path. Relative paths resolve from `demo/ocr`, not the kernel. |
| `CONTENTUNDERSTANDING_ENDPOINT` | Your CU resource endpoint. Without it, local preprocessing runs and service requests are explicitly skipped. |
| `CONTENTUNDERSTANDING_KEY` | Optional; leave blank to use Microsoft Entra ID. |
| `CU_ANALYZER_ID` | The existing analyzer used for extraction. Set explicitly; the notebooks do not silently substitute another analyzer or invent a field schema. |
| `CU_API_VERSION` | Same API for every comparison, default `2025-11-01`. |
| `OCR_TARGET_DPI` | Render resolution, default 300. |
| `OCR_FOCUS_PAGE` | One-based page for full-page previews, default 1. No crop coordinates are required. |
| `OCR_MINUS_BOX` | Optional sign-region box for a local image diagnostic. |
| `OCR_KEYWORD` | Label to preview; finding it alone is not an accuracy score. |
| `OCR_EXPECTED_AMOUNTS` | Local CSV with `page,label,amount`, read from the visible document. |
| `OCR_REDACT_BOXES` | Optional local black-out boxes for a separate reproduction-candidate test. |

Only the OCR folder's `.env` is read. There is no repository-root configuration fallback.

Previews show complete pages, and every main CU input retains all pages. The notebooks print absolute paths for the original PDF, generated TIFFs, preview images and CU result files so you can open the originals directly. Preview downscaling does not change the file submitted to CU.

## Compare the correct outputs

- Keep the input document, page coverage, endpoint, analyzer and API fixed; change only preprocessing.
- Use the **actual field-extraction analyzer** to assess business fields. `prebuilt-layout` returns OCR/layout, not the payout-field contract.
- Notebook 04 exports the complete typed fields returned by CU and shows compact side-by-side previews when fields are present.
- Its `kept`/`lost`/`wrong sign`/`not found`/`ambiguous` checks apply to amounts in CU Markdown, not automatically to business fields. Zero returned fields is explicitly reported, never treated as validated field extraction.
- Expected values are evaluation data only; they are not sent to CU and are never used to repair an extracted sign.
- Rendering preserves visible page layers but cannot recover detail absent from the source. 300 dpi and filters are experiments, not guaranteed improvements.
- A passing original means the missing-sign symptom was not reproduced in that run. Compare failing and non-failing scans before changing an ingestion pipeline.

The existing local results were produced with `prebuilt-layout`. They remain useful OCR diagnostics but do not validate the business extraction analyzer.

## Saved results and costs

A cache miss makes a billable CU request. Cache entries depend on exact input bytes, endpoint, analyzer and API. Re-running unchanged cases reuses their responses. If an analyzer is updated under the same ID, move its old cache aside before comparing new results.

| Local output | Contents |
|---|---|
| `output/results.csv` | Per-case Markdown checks, analyzer and returned field count. |
| `output/cu_fields_by_case.json` | Complete typed field values returned by the selected analyzer. |
| `output/amount_details.csv` | Per-page/label Markdown value and sign checks. |
| `output/comparison.html` | Local comparison report and full-page previews. |
| `output/cu-cache/` | Full service responses. |
| `output/executed/` | Optional local executed copies; source notebooks remain without outputs. |

An optional redaction candidate is a separate single-page test, not a main comparison case. It needs human privacy review and must still exhibit the same failure before being described as a reproduction.

## Reused source

- [Official Azure SDK binary-analysis sample](https://github.com/Azure/azure-sdk-for-python/blob/53023a2cd9adf255cff520a99985fff84dc58d7d/sdk/contentunderstanding/azure-ai-contentunderstanding/samples/sample_analyze_binary.py): client, request, polling and response handling. [Microsoft MIT notice](LICENSE).
- [Existing PDF renderer](https://github.com/jomedinagomez/azure-ai-foundry-insurance/blob/f6949572c5aaa6bc77b1ac592a92affc62d98346/demo/sov/preprocess/pdf_render.py): PDFium rendering and lossless multi-page TIFF pattern.
- [OpenCV non-local-means example](https://github.com/opencv/opencv/blob/55ff746075718ec2d7cfe09b106c070555f3dbff/doc/py_tutorials/py_photo/py_non_local_means/py_non_local_means.markdown), [morphology](https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html) and [Pillow filters](https://github.com/python-pillow/Pillow/blob/98fa02d46db2bc96f04521e5989d08a8b6083c9f/src/PIL/ImageFilter.py).
- [CU analyzers](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/prebuilt-analyzers) and [supported inputs/limits](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/service-limits).

Keep documents, expected amounts, `.env`, service responses, screenshots and the local slide deck out of public commits. `input/`, `output/` and the local configuration/deck are Git-ignored; tracked notebooks should have empty outputs and null execution counts.
