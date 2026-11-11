# Build brief for GitHub Copilot: `demo/ocr` sample notebooks

> Implementation note: the active workflow starts at notebook 02 and always takes a scanned PDF. Notebooks 02-04 compare the original scan and preprocessed versions through the same configured Content Understanding analyzer. Notebook 01, intake-image extraction, shared helpers and synthetic generation are not required. See `README.md` for current paths and settings; the detailed design below is historical reference, not the current file inventory.

> How to use: open the `azure-ai-foundry-insurance` repo on branch `feat/ocr-notebook-guidance`, add `demo-ocr-README.md` to the folder as `demo/ocr/README.md`, then paste this brief into Copilot Chat in agent mode, or create a GitHub issue with it and assign the issue to Copilot.

## Task

Create the sample code that `demo/ocr/README.md` describes: a shared helper module, a synthetic sample generator and four notebooks. They show how to preprocess faxed and scanned PDF pages before Azure AI Content Understanding, so small marks such as a minus sign survive OCR. Every notebook ends by sending its result to Content Understanding and checking the sign of each amount.

## Before you start

1. `demo/ocr/` already exists on this branch. Read what is there first. Keep what fits, and don't delete or overwrite a file without saying why in the pull request.
2. Read `demo/sov/preprocess/pdf_render.py` and `demo/sov/notebooks/02_xlsx_via_pdf_tiff.ipynb`. Reuse their PDF rendering and Content Understanding client code where it fits, and keep one PDF library across the repo.
3. Follow the repo's conventions: a `.env.example` per demo folder, the `uv` setup in the top-level README, notebooks committed without outputs or execution counts, and no emojis.

## Files to create

| Path | Purpose |
|---|---|
| `demo/ocr/README.md` | The guide (provided). Keep its file table, steps and settings in sync with what you build. |
| `demo/ocr/.env.example` | `CONTENTUNDERSTANDING_ENDPOINT=`, `CONTENTUNDERSTANDING_KEY=` (optional), `CU_ANALYZER_ID=prebuilt-layout` |
| `demo/ocr/.gitignore` | Ignore `input/`, `output/` and `.env` |
| `demo/ocr/fax_preprocess.py` | Helpers shared by every notebook (spec below) |
| `demo/ocr/make_fax_samples.py` | Synthetic faxed statements and expected amounts (spec below) |
| `demo/ocr/samples/` | Output of `make_fax_samples.py`, committed so the notebooks run without generating |
| `demo/ocr/01_source_image.ipynb` | Step 1: get the source image and send it instead of the PDF |
| `demo/ocr/02_rescale_300dpi.ipynb` | Step 2: rescale to 300 dpi, and the render shortcut |
| `demo/ocr/03_denoise_sharpen.ipynb` | Step 3: denoise and sharpen, plus the techniques to test or avoid |
| `demo/ocr/04_compare_results.ipynb` | Every version through Content Understanding, sign by sign, and a redacted sample to share |

## `fax_preprocess.py`

Small, typed, documented functions. Use Pillow for images, NumPy for pixel checks and OpenCV only where Pillow has no equivalent.

| Function | Behaviour |
|---|---|
| `inspect_pdf(path) -> list[dict]` | One dict per page: page size in points; each image's name, filter (`CCITTFaxDecode`, `JBIG2Decode`, `DCTDecode`, `FlateDecode`…), pixel size and bits per component; effective x and y dpi from the image's placed size on the page (fall back to the page size); fax mode (`standard` near 204 × 98, `fine` near 204 × 196, else `other`); whether the page has a text layer, and whether it is drawn invisibly (text render mode 3, the `3 Tr` operator) |
| `page_text_layer(path, page) -> str` | The page's embedded text, so a notebook can show whether it contains the minus |
| `extract_source_image(path, page) -> tuple[Image, float, float]` | The page's full-page image exactly as stored, with its x and y dpi. No resampling and no colour change. If the page has no image, several image strips or a filter that can't be decoded (for example JBIG2 without `jbig2dec`), raise an error that says so and suggests `render_page` |
| `load_source_image(path, xdpi=None, ydpi=None) -> tuple[Image, float, float]` | Open a TIFF or PNG from the source system, including multi-page TIFF. Read the dpi tags, and require `xdpi` and `ydpi` when the tags are missing |
| `rescale_to_dpi(img, xdpi, ydpi, target=300) -> Image` | Convert mode `1` or `P` to `L` first (Pillow scales mode `1` with nearest neighbour only), then resize to `round(w * target / xdpi)` × `round(h * target / ydpi)` with Lanczos |
| `render_page(path, page, dpi=300) -> Image` | Draw the whole page as a new grayscale image at `dpi`. Reuse `pdf_render.py` if it can return one page |
| `save_lossless(img, path, dpi)` | Write TIFF (Group 4 for mode `1`, LZW or Deflate otherwise) or PNG, always with `dpi` set. Raise `ValueError` for `.jpg` or `.jpeg` |
| `denoise(img, size=3)` and `denoise_nlmeans(img, h=10)` | Median filter (Pillow) and non-local means (`cv2.fastNlMeansDenoising`), grayscale only |
| `sharpen(img, radius=1.0, percent=100, threshold=2)` | Pillow `ImageFilter.UnsharpMask` |
| `thicken(img, rows=2, cols=1)` | Grow dark strokes with a minimum filter. On dark-on-white pages that is `cv2.erode`, not `cv2.dilate`; say so in a comment. Test only |
| `thin(img, rows=2, cols=1)` and `binarize_otsu(img)` | For the "avoid" demonstrations only |
| `analyze(data, content_type, analyzer_id=None) -> dict or None` | Content Understanding through the `azure-ai-contentunderstanding` package: `begin_analyze_binary`, GA API `2025-11-01` (the SDK default). Use the key when `CONTENTUNDERSTANDING_KEY` is set, otherwise `DefaultAzureCredential`. Default analyzer `prebuilt-layout`, overridable with `CU_ANALYZER_ID`. Cache results in `output/cu-cache/`, keyed by file hash and analyzer ID. Without an endpoint, print "skipped: set CONTENTUNDERSTANDING_ENDPOINT" and return `None` |
| `markdown_of(result) -> str` | The markdown of the first content item |
| `find_signed_amounts(text) -> list[dict]` | Money amounts with their sign and style: leading minus (`-`, `−` U+2212, `–`), parentheses, trailing minus and `CR` suffix; thousands separators; two decimals |
| `compare_signs(expected, text) -> pandas.DataFrame` | For each expected amount: `kept`, `lost` (found without its sign) or `not found` |
| `show(images, titles, crop=None, zoom=4)` | Side-by-side matplotlib view at the same physical size, with nearest-neighbour zoom so single pixels stay visible |

## `make_fax_samples.py`

- Fictional data only: an obviously made-up lender and borrowers, and no real names, addresses or account numbers.
- Three one-page statements with about ten line items each. Include at least four negative amounts, one in each style: `-2,450.00`, `(980.40)`, `75.10-` and `310.00 CR`.
- Draw each page as vector (reportlab, 9–10 pt Helvetica). Render it at 204 dpi across, resample it to 98 lines per inch (standard) or 196 (fine), threshold it to black and white, and add light speckle from a seeded random generator.
- Save, for each statement and mode:
  - `<name>_<mode>.tif`: the fax image as a source system would keep it (Group 4, dpi tags 204 × 98 or 204 × 196)
  - `<name>_<mode>.pdf`: an image-only PDF with the bitmap over the whole page, as a fax server would wrap it (`img2pdf` keeps the Group 4 data as is)
  - `<name>_<mode>_textlayer.pdf`: the same PDF plus an invisible text layer (render mode 3) in which the minus signs, parentheses and `CR` are missing, to test the hidden-text-layer suspect
- Write `samples/expected_amounts.csv` (`file,page,label,amount`, with signed amounts), `samples/layout.json` (each amount's box on the page, in inches, so notebooks can crop it) and `samples/redact_boxes.json` (boxes for the borrower name and address).
- Deterministic (fixed seed), no network, under 30 seconds.

## Notebooks

Every notebook has a title cell that says which recommendation it shows and when to use it, a markdown cell before each step that says why, short code cells that call `fax_preprocess.py`, and a closing "Takeaways" cell. It defaults to the samples; a `FILES` cell at the top lets the reader point it at `input/` instead.

### `01_source_image.ipynb`

1. What the source image is, and the two ways to get it.
2. Inspect a sample PDF with `inspect_pdf`: filter, pixel size, x and y dpi, fax mode, text layer and whether it is invisible. Print the text layer near each amount.
3. Option A: load the source system's original (`samples/*_standard.tif`).
4. Option B: extract the image from the PDF unchanged. Assert that it is pixel-identical to option A.
5. Save it lossless to `output/`.
6. Send the PDF and the source image to Content Understanding and compare signs with `compare_signs`.
7. Takeaways: if the source image keeps the sign and the PDF doesn't, the PDF or its text layer was the cause. If a sign is still lost, go to 02.

### `02_rescale_300dpi.ipynb`

1. Why square pixels, with the factors for standard and fine mode. 300 dpi is a common OCR choice, not a Content Understanding requirement.
2. Load the source image from 01's output, or extract it again.
3. Rescale with `rescale_to_dpi`. Print the new size (a letter page becomes 2,550 × 3,300 px) and show one negative amount before and after at the same physical size.
4. Render shortcut: `render_page` at 300 dpi. Compare it with extract-then-rescale, side by side and as a mean absolute pixel difference. Note that rendering doesn't draw the invisible text layer.
5. Save both lossless, send both to Content Understanding and compare signs.
6. Takeaways.

### `03_denoise_sharpen.ipynb`

1. Only if a sign still drops after 02. Filters run on the 300 dpi image, never on the raw fax.
2. Use: a 3 × 3 median (non-local means as an option), then a light unsharp mask. Show crops.
3. Test only: `thicken` with a 2 × 1 vertical kernel. Show that speckle grows too and digits can merge.
4. Avoid, shown with numbers: count the dark pixels in the minus box (from `layout.json`) after (a) the same median filter on the raw fax, (b) `thin` and (c) `binarize_otsu`. On a standard-mode sample the minus should drop to zero or close to it.
5. Send the kept variants to Content Understanding. Keep a filter only if failing documents improve and none get worse.
6. Takeaways.

### `04_compare_results.ipynb`

1. The comparison: for each file, send the original PDF, the source image as is, the source image rescaled, the 300 dpi render and, optionally, the filtered image.
2. Build each version losslessly in `output/versions/`, analyze it with caching and check signs against `expected_amounts.csv`.
3. Results: a table of file × version with kept, lost and not-found counts, saved as `output/results.csv`. Call out the versions that keep every sign.
4. Shareable sample: take the extracted source image of a failing page, black out the boxes in `redact_boxes.json`, save it lossless and analyze it again. Share it only if the sign is still lost; if redaction changes the result, say so.
5. Takeaways: what to change in production, in the README's order.

## Dependencies

Add to the top-level `requirements.txt` only what is missing: `azure-ai-contentunderstanding`, `azure-identity`, `python-dotenv`, `pillow`, `numpy`, `pandas`, `matplotlib`, `opencv-python-headless`, `reportlab`, `img2pdf` and a PDF library. Reuse the one `pdf_render.py` already uses; if it doesn't fit, use `pypdf` to extract and `pypdfium2` to render, both permissively licensed.

## Rules

- Content Understanding is the only OCR. Don't add Tesseract, EasyOCR or any other OCR engine, and don't call a language model directly.
- No AI upscaling or super-resolution.
- Never write JPEG. Every saved image is TIFF or PNG, with its dpi set.
- Don't re-binarise a faxed image, except in the "avoid" demonstration.
- Synthetic data only. No customer names, documents, screenshots or IDs anywhere: code, comments, notebooks, file names or commit messages.
- No secrets in code. Read settings from `.env`, and prefer Microsoft Entra ID to keys.
- Each notebook runs top to bottom with no endpoint set: the image steps run, and the Content Understanding cells say they were skipped.
- Keep it readable for customers: short cells, plain names and no clever one-liners.

## Done when

- [ ] `python demo/ocr/make_fax_samples.py` regenerates `samples/` identically (fixed seed).
- [ ] Each notebook runs top to bottom, with and without an endpoint.
- [ ] In 01, the extracted image is pixel-identical to the matching `.tif` for every sample.
- [ ] In 02, a standard-mode letter page comes out at 2,550 × 3,300 px and 300 dpi.
- [ ] In 03, the "avoid" demonstrations show the minus erased on the raw fax and kept after rescaling.
- [ ] 04 writes `output/results.csv` and prints the summary table.
- [ ] `save_lossless` refuses `.jpg` and `.jpeg`.
- [ ] `README.md` lists exactly the files in the folder, and every link in it works.
- [ ] Notebooks are committed without outputs.

## Links to the files

These work once the files are on the branch. After merging to `main`, replace `feat/ocr-notebook-guidance` with `main`.

| File | Link |
|---|---|
| Folder | https://github.com/jomedinagomez/azure-ai-foundry-insurance/tree/feat/ocr-notebook-guidance/demo/ocr |
| `README.md` | https://github.com/jomedinagomez/azure-ai-foundry-insurance/blob/feat/ocr-notebook-guidance/demo/ocr/README.md |
| `01_source_image.ipynb` | https://github.com/jomedinagomez/azure-ai-foundry-insurance/blob/feat/ocr-notebook-guidance/demo/ocr/01_source_image.ipynb |
| `02_rescale_300dpi.ipynb` | https://github.com/jomedinagomez/azure-ai-foundry-insurance/blob/feat/ocr-notebook-guidance/demo/ocr/02_rescale_300dpi.ipynb |
| `03_denoise_sharpen.ipynb` | https://github.com/jomedinagomez/azure-ai-foundry-insurance/blob/feat/ocr-notebook-guidance/demo/ocr/03_denoise_sharpen.ipynb |
| `04_compare_results.ipynb` | https://github.com/jomedinagomez/azure-ai-foundry-insurance/blob/feat/ocr-notebook-guidance/demo/ocr/04_compare_results.ipynb |
| `fax_preprocess.py` | https://github.com/jomedinagomez/azure-ai-foundry-insurance/blob/feat/ocr-notebook-guidance/demo/ocr/fax_preprocess.py |
| `make_fax_samples.py` | https://github.com/jomedinagomez/azure-ai-foundry-insurance/blob/feat/ocr-notebook-guidance/demo/ocr/make_fax_samples.py |
