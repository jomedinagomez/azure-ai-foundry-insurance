# Official Content Understanding demos

Reused from [Azure-Samples/azure-ai-content-understanding-python](https://github.com/Azure-Samples/azure-ai-content-understanding-python/tree/19f1a9d68ef5de66abef056564f32e4bc49f4067/notebooks),
pinned to commit `19f1a9d68ef5de66abef056564f32e4bc49f4067`.
The original MIT [license](LICENSE), REST sample client, helpers, analyzer templates,
and sample media are included. These educational samples are separate from the
[claims RAG notebooks](../rag/notebooks/) and do not replace the app's SDK implementation.

## Multimodal walkthrough

| Notebook | Inputs and demonstration |
|---|---|
| [Content extraction](notebooks/content_extraction.ipynb) | PDF file and public PDF URL; WAV transcription; MP4 video, transcript, timestamps and downloaded keyframes. |
| [Field extraction](notebooks/field_extraction.ipynb) | Invoice PDF and receipt PNG with prebuilt analyzers; custom invoice schema. |
| [Classifier](notebooks/classifier.ipynb) | Mixed financial PDF; classification, splitting and routing to a custom loan analyzer. |

Open each notebook in VS Code, select the repository's root **.venv**, and run
cells in order. The setup locates the root `.env`, uses
`APP_CONTENT_UNDERSTANDING_ENDPOINT`, and authenticates with Microsoft Entra ID.
No subscription-key fallback is used. Azure CLI authentication is selected by
the repository's existing `AZURE_TOKEN_CREDENTIALS` setting.

The existing environment is reused; automatic `%pip install` cells are disabled.
The copied [upstream requirements](requirements.txt) describe the sample dependencies.
Install a missing dependency only if execution reports it.

### Deliberately small local adaptations

- The upstream analysis calls, sample schemas and helper implementation are reused.
- The default-update example is a **read-only** defaults check. No models are
  deployed and no resource-wide model mappings are patched.
- Custom analyzers use the existing model mapping for
  `APP_CU_COMPLETION_DEPLOYMENT`, rather than assuming a `gpt-4.1` deployment.
- Notebook displays show short Markdown/JSON previews and five transcript entries;
  the complete native results are still saved by the upstream code.
- Notebook headings, messages and saved display outputs are emoji-free. The
  shared JSON saver's status message is plain text; extracted data and media are unchanged.
- Sample-created analyzer deletion requires explicitly setting
  `RUN_SAMPLE_CLEANUP=True`. By default those uniquely named sample analyzers are
  retained for inspection. Running the notebooks again makes new sample analyzers
  and incurs additional Azure usage.

## Shareable results

All three walkthrough notebooks have been executed using the root `.venv`:
**30 successful code cells**, including document, receipt-image, audio, video,
custom-field and classifier calls. Their populated output cells are retained.
The largest text output is under 7,000 characters; full native JSON is stored
separately rather than printed into the notebooks.

Save executed notebooks with their output cells intact. Full JSON results and
up to three downloaded video keyframe files are written under
`notebooks/test_output/`, including the custom-invoice result. The upstream
video preview displays its first segment, not the full video's duration; shared
segment boundaries can produce duplicate downloaded keyframes. The full JSON
retains all segments and timestamps. Source media remains under [data](data/).
Keep these folders together when sharing so relative paths continue to work.
Video and audio source files are not embedded as large base64 notebook outputs.

The [source manifest](upstream-source.json) records the pinned upstream paths,
Git blob IDs and SHA-256 values of the original downloaded bytes. Its
`localAdaptations` and `referenceRelocations` entries distinguish the adapted
notebooks from unchanged upstream files; execution naturally changes notebook
hashes. Media files are real Git LFS contents, not pointer files.

## Reference only: management and training

The other two upstream notebooks are preserved unchanged in a separate folder:

- [Analyzer management](reference-notebooks/management.ipynb)
- [Analyzer training](reference-notebooks/analyzer_training.ipynb)

They are **not part of the executed multimodal walkthrough**. Management examples
can change defaults or delete analyzers. Training requires separate labeled Blob
data and its own configuration; those training resources are not provisioned
here. Review their upstream prerequisites and obtain approval before running them.

## References

- [Upstream notebook collection](https://github.com/Azure-Samples/azure-ai-content-understanding-python/tree/main/notebooks)
- [Content Understanding documentation](https://learn.microsoft.com/azure/ai-services/content-understanding/)
- [Content Understanding REST API](https://learn.microsoft.com/rest/api/contentunderstanding/)
- [Current and proposed claims architecture](../architecture/)
