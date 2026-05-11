"""PDF rendering primitives for the SOV pipeline.

Two functions:

- `convert_libreoffice(xlsx, out_dir)` runs `soffice --headless --convert-to
  pdf:calc_pdf_Export` and returns the path to the resulting vector PDF.
- `rasterize_pdf_to_tiff(pdf, out_dir, dpi=800)` renders each PDF page to a
  high-DPI PNG and assembles them into a single multi-page LZW TIFF. We send
  this to CU instead of the vector PDF because layout analysis on vector
  PDFs of borderless tables mis-merges adjacent rows (see
  `feedback/underwriting/research-output/pdfs/BUG_REPORT.md`). Rasterizing
  forces the OCR path, which uses pure spatial geometry and produces
  deterministic row identity.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


_WINDOWS_FALLBACKS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)


def find_libreoffice() -> str | None:
    """Locate the `soffice` (LibreOffice) binary. Returns None if not found."""
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for p in _WINDOWS_FALLBACKS:
        if Path(p).exists():
            return p
    return None


def convert_libreoffice(
    xlsx_path: str | Path,
    out_dir: str | Path,
    *,
    soffice_path: str | None = None,
    timeout: int = 180,
) -> Path:
    """Convert an xlsx to a vector PDF using LibreOffice's Calc PDF exporter.

    Raises RuntimeError if LibreOffice isn't installed or the conversion fails.
    """
    xlsx_path = Path(xlsx_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    soffice = soffice_path or find_libreoffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice not found. Install it (Linux: `apt-get install -y "
            "libreoffice-calc`; Windows: `winget install "
            "TheDocumentFoundation.LibreOffice`) or pass soffice_path=..."
        )

    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--convert-to",
        "pdf:calc_pdf_Export",
        "--outdir",
        str(out_dir),
        str(xlsx_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    pdf = out_dir / (xlsx_path.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError(
            f"LibreOffice did not produce PDF.\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        )
    return pdf


def rasterize_pdf_to_tiff(
    pdf_path: str | Path,
    out_dir: str | Path,
    *,
    dpi: int = 800,
) -> Path:
    """Render every PDF page to a single multi-page LZW TIFF.

    CU accepts `image/tiff` directly via `begin_analyze_binary`; a multi-page
    TIFF becomes one analyze call with N `contents` entries (one per page).

    Default DPI is 800 because 600 DPI clips parentheses on phone numbers
    in our test corpus. 800 closes the last OCR drift on Acme (1 acct miss
    at 600 → 0 at 800). See research notebook for the full DPI ablation.
    """
    import pypdfium2 as pdfium
    from PIL import Image

    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    src = pdfium.PdfDocument(str(pdf_path))
    scale = dpi / 72.0
    imgs: list[Image.Image] = [
        page.render(scale=scale).to_pil().convert("RGB") for page in src
    ]
    if not imgs:
        raise RuntimeError(f"no pages in {pdf_path}")

    tiff = out_dir / (pdf_path.stem + ".tiff")
    imgs[0].save(
        tiff,
        "TIFF",
        save_all=True,
        append_images=imgs[1:],
        compression="tiff_lzw",
        dpi=(dpi, dpi),
    )
    return tiff
