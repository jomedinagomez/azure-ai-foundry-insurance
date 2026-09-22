# Analyzer Workshop forms demo

The **Analyzer Workshop** tab replaces the Content Understanding Studio project
workflow for this demo. A customer can upload local PDFs, prepare OCR for manual
labeling or auto-label one document with a named analyzer, review and adjust the
fields, move to the next document, and export the reviewed data without a
storage account or storage credentials.

## UI workflow

1. Start the workshop API and web app, then open **Analyzer Workshop**.
2. Create a forms project. The preset contains the 14 property-claim fields.
3. Add PDFs to **Training** and **Evaluation**.
4. For each document, choose **Prepare OCR** for manual labeling or **Auto
   label** with the analyzer ID shown in the field.
5. Select text in the OCR pane and apply it to a field, or adjust an auto-label.
6. Select **Reviewed and next** to save the labels and advance through the queue.
7. Select **Export labels** to download one ZIP containing the reviewed source,
   result, and label triplets plus the analyzer template and manifest.
8. When the API host has Azure storage configured, select **Build learned** and
   then **Score** to compare the learned and zero-shot analyzers against reviewed
   evaluation values.

All project files stay under the ignored `.workbench/` directory. Authoring
routes are loopback-only and the standalone API binds to `127.0.0.1` by default.

## Storage boundary

Local labeling and export do not use Blob storage. Content Understanding still
requires a Blob `containerUrl` to train from labeled examples; a local path
cannot be supplied as a `labeledData` knowledge source.

For **Build learned**, the API host creates an isolated per-project container,
uploads only reviewed training triplets, provides a short-lived read/list SAS to
Content Understanding, waits for `2026-06-01-preview` training to finish, and
deletes the container. The customer never receives storage credentials or uses
a Studio project. The preview API is used because it distills the labeled
patterns into the analyzer and does not require the samples at analysis time.

## Self-contained notebook

[`notebooks/01_build_and_compare_from_export.ipynb`](notebooks/01_build_and_compare_from_export.ipynb)
takes the ZIP exported by the UI. Edit the ZIP path, set `RUN_AZURE = True`, and
run the seven cells in order. It independently validates the package, creates
both GPT-5.2 analyzers, removes temporary staging after training, runs one
reviewed evaluation PDF through both analyzers, and exports a field comparison.
It imports no repository helper modules.

The fixed sample manifest in [`reference/ground-truth.json`](reference/ground-truth.json)
remains available for automated tests, but it is not required by the customer
workflow.

## Interpretation

Accuracy against reviewed values is the decision criterion. Confidence alone is
not accuracy, and labeled examples do not repair OCR glyph errors such as
reading `78` as `74`.

Official references:

- [Improve a document analyzer with labeled samples](https://learn.microsoft.com/azure/ai-services/content-understanding/document/analyzer-improvement)
- [Content Understanding analyzer reference](https://learn.microsoft.com/azure/ai-services/content-understanding/concepts/analyzer-reference)
