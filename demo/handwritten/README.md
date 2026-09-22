# Handwriting analyzer

[`handwritten_analyzer.ipynb`](handwritten_analyzer.ipynb) is a self-contained
GPT-5.2 property-claim extraction demo. Set its local input paths, set
`RUN_AZURE = True`, and run the cells in order.

For each information field, the custom Content Understanding schema returns a
value, a handwriting judgment, a separate handwriting score, and evidence. The
notebook also runs Document Intelligence Layout and reports its native
`styles[].isHandwritten` signal. These signals are shown separately because
Content Understanding does not expose a native handwriting flag and extraction
confidence is not handwriting confidence.

The notebook uses local PDF or image inputs and writes reviewed JSON and CSV
under the ignored `output/` directory. Full CU/DI responses can contain OCR text
and are disabled by default; set `SAVE_RAW_RESPONSES = True` only when that local
diagnostic output is appropriate. It does not use Content Understanding Studio,
projects, or Blob storage.