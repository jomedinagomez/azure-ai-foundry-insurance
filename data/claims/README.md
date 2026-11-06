# Six fictional claim packets

This is a simple demo using **MSG, PDF, JPG and PNG**. Each folder tells one
cohesive claim story; the goal is representative evidence, not exhaustive
file-extension coverage.

Complementary system-of-record data and claim log notes live separately in
[claims-operations](../claims-operations/README.md) and are exposed by a read-only
local API. They are not additional files to ingest into the document index.

These are finished source files, not a generator or an application. Every
business, person, policy, event, amount and correspondence item is fictional.
The damage photos are photorealistic AI-generated images, not actual incident
photographs. Documents and images must not be used to support a real claim.

## Folder structure

Each claim folder contains mixed original files: documents, emails, images and
structured exports together. Filenames such as `policy.pdf` and `inspection.pdf`
repeat across claims, but the claim references and contents differ.

| Folder | Scenario | Cases to inspect |
|---|---|---|
| [claim-001](claim-001/) | Warehouse wind damage and water entry | Annotated roof photos, bay/access diagram, moisture readings and conflicting reported time |
| [claim-002](claim-002/) | Restaurant fire and smoke contamination | Hood/ceiling photos, extraction sketch, uninspected duct and disputed replacement scope |
| [claim-003](claim-003/) | Commercial van damage | Rear-left damage photos and location sketch; email thread, forwarded message and missing revised PDF |
| [claim-004](claim-004/) | Reported retail slip | Later site photos and aisle diagram; disputed warning-sign timing and incomplete cleaning log |
| [claim-005](claim-005/) | Storage-unit damage and reported missing property | Latch/lock photos and entrance sketch; interior not shown and unverified contents count |
| [claim-006](claim-006/) | Workshop water ingress | Wet-stock photos and site diagram; unresolved ingress route and a later email-only PDF proposal |

## Files and relationships

- Each `inspection.pdf` contains four pages: narrative, itemized preliminary
  estimate, annotated photographic exhibit, and a case-specific diagram.
  The photos and diagram are embedded **inside the PDF**, not just linked to
  loose images or supplied as email attachments.
- The policy, notification and inspection belong to the same claim. Original
  JPGs remain unmarked; annotations describe visible appearances without
  deciding cause, timing, liability or coverage. Incident scans are image-only.
- MSG files are genuine Unicode Outlook messages. Each claim's
  `02-inspection-and-attachments.msg` includes:
  - `inspection-review-copy.pdf`: byte-identical to the loose `inspection.pdf`.
  - `emergency-authorization.pdf` and `site-access.png`: attachment-only evidence,
    intentionally absent as loose source files.
- An inline signature PNG is branding, not a damage photo. The email-heavy
  claim also includes a forwarded MSG attachment.
- In claim-006, `04-revised-proposal.msg` supplies an attachment-only PDF with
  the later scope. Preserve the earlier inspection and distinguish both from
  the internal reserve; none represents an agreed payment.

ZIP, Office/legacy, EML, structured-export, extensionless and audio/video examples
have been removed from the demo input folders. Email attachments also use only
MSG, PDF, JPG and PNG.

## Inspection aids

- [inventory.csv](inventory.csv): source paths, MIME types, sizes, SHA-256 hashes
  and PDF page counts.
- [attachment-inventory.json](attachment-inventory.json): email parentage,
  attachment-only items, inline-image roles and exact loose-file matches.
- [review-notes.json](review-notes.json): expected claim facts, contradictions,
  embedded report-page locations and a few visual-review questions.

These inspection aids are metadata outside the claim folders, not additional
inputs. Keep them out of source retrieval when evaluating extraction.

The six folders contain 62 source files. This is a small functional demo, not
a recreation of the customer's volumes, file sizes or private schema.

No OCR, Markdown extraction, chunking or indexing has been run. When processing
these files, preserve originals and place derived Markdown, extracted images,
attachments and chunks in a separate output directory grouped by claim.
