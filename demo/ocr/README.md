# OCR investigation for faxed documents

Three independent notebooks illustrate the input comparisons described in the accompanying presentation. They reuse source examples rather than introduce another client or processing framework.

| Notebook | What it does |
|---|---|
| [01 - Compare the PDF and intake image](notebooks/01_compare_pdf_and_source_image.ipynb) | Submit the original PDF and, if available, the original fax image to the same CU analyzer. Save the full responses and inspect the affected text. |
| [02 - Render a PDF to TIFF](notebooks/02_render_pdf_to_tiff.ipynb) | Adapt the existing PDF renderer to 300 dpi grayscale, lossless multi-page TIFF, then compare the PDF and TIFF with the same analyzer. |
| [03 - Test optional filters](notebooks/03_test_denoising_and_sharpening.ipynb) | Compare a grayscale control, light denoising and light sharpening on the same image. All pages are retained. Filters are experiments, not automatic fixes. |

Each notebook contains its own setup, processing and analysis cells. No notebook imports another notebook or a local helper script.

## Setup

1. Use Python 3.12 and install `pip install -r requirements.txt` in your selected environment.
2. Copy [.env.example](.env.example) to `.env` and set your Content Understanding resource endpoint. Sign in with `az login` using an identity authorized to analyze documents on that resource.
3. Keep approved documents in a local `input/` directory here. No production samples are included.
4. Open a notebook with its working directory set to `notebooks/`. Edit the input paths before running cells.

The default analyzer is `prebuilt-layout`, with GA API `2025-11-01`. It returns OCR/layout content without requiring a completion or embedding model. See [prebuilt analyzers](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/concepts/prebuilt-analyzers). To compare an existing analyzer, set the same analyzer ID in all cases and record that change; do not compare different configurations as if only the image changed.

Local preprocessing cells do not call Azure. The clearly marked analysis cells do: notebook 01 makes one PDF call and optionally one source-image call; notebook 02 makes two calls; notebook 03 makes three calls. Each cell execution submits fresh requests, which incur service charges. There are no retries or background runners.

Full results, Markdown and input hashes are saved under the ignored `output/` directory. Only a short text preview is displayed. The cells do not infer missing signs, fix financial values or automatically declare a variant correct.

## How to interpret the comparison

- Preserve the exact original bytes; re-saving, redacting or rendering can change the reproduction.
- Prefer the original intake image when available. These examples do not extract embedded images from a PDF or remove protection.
- A 300 dpi render creates a different raster input and removes the PDF text layer from the submitted derivative. It does **not** recover detail absent from the source.
- Denoising and sharpening can erase or distort a thin minus sign. Keep a filter only after checking known failures and representative non-failing documents.
- Inspect the monetary value, sign and its surrounding label against the source pixels. A keyword match or plausible positive amount is not proof of correct OCR.
- Re-test the actual extraction analyzer after isolating the OCR symptom. No failure frequency or universal correction is established here.
- Born-digital documents are not automatically routed through this fax-specific experiment.

No sample is uploaded when opening a notebook. `input/`, `output/` and `.env` are ignored by Git. Before committing a notebook after using real documents, clear its cell outputs: `.gitignore` cannot protect text or images saved inside a tracked notebook.

## Source code and adaptations

Each notebook also cites its sources next to the relevant cells.

| Source | Reuse and changes |
|---|---|
| [Azure SDK binary-analysis sample](https://github.com/Azure/azure-sdk-for-python/blob/53023a2cd9adf255cff520a99985fff84dc58d7d/sdk/contentunderstanding/azure-ai-contentunderstanding/samples/sample_analyze_binary.py) | Same `ContentUnderstandingClient`, `begin_analyze_binary` and `poller.result()` flow. Adapted for interactive cells, Entra-only authentication, `prebuilt-layout`, local response saving and compact previews. Microsoft MIT notice: [LICENSE](LICENSE). |
| [Existing PDF renderer](https://github.com/jomedinagomez/azure-ai-foundry-insurance/blob/f6949572c5aaa6bc77b1ac592a92affc62d98346/demo/sov/preprocess/pdf_render.py) | Same PDFium scale calculation and Pillow `save_all`/`append_images`/LZW TIFF pattern. Adapted from 800 dpi RGB to 300 dpi grayscale; no margin trimming. |
| [OpenCV non-local-means tutorial source](https://github.com/opencv/opencv/blob/55ff746075718ec2d7cfe09b106c070555f3dbff/doc/py_tutorials/py_photo/py_non_local_means/py_non_local_means.markdown) | Uses the documented single-grayscale `fastNlMeansDenoising` API with light starting parameters. The filter implementation is imported, not copied. |
| [Pillow UnsharpMask source](https://github.com/python-pillow/Pillow/blob/98fa02d46db2bc96f04521e5989d08a8b6083c9f/src/PIL/ImageFilter.py) | Uses the existing filter implementation with explicit radius, percent and threshold. No new sharpening algorithm. |

Additional guidance: [Tesseract image quality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html), [CU supported inputs and limits](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/service-limits), [PDFium rendering](https://pypdfium2.readthedocs.io/en/stable/python_api.html), [Pillow TIFF format](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#tiff), [OpenCV denoising](https://docs.opencv.org/4.x/d5/d69/tutorial_py_non_local_means.html), [Pillow UnsharpMask](https://pillow.readthedocs.io/en/stable/reference/ImageFilter.html#PIL.ImageFilter.UnsharpMask).

Tesseract's advice is useful preprocessing background; it does not establish that Content Understanding uses Tesseract or that its suggested settings are appropriate for a particular fax.
