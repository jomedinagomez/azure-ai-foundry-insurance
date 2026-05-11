"""SOV preprocessing primitives.

xlsx → page-setup preflight → vector PDF → high-DPI multi-page TIFF.
Used by:
- the production-shape demo notebook `04_xlsx_via_pdf_tiff.ipynb`
- the workshop app pipeline registry (Phase W2.1)

Research evidence behind the technique:
- `feedback/underwriting/research_xlsx_to_pdf.ipynb`
- `feedback/underwriting/research-output/pdfs/BUG_REPORT.md`
"""

from .xlsx_preflight import (
    apply_print_preflight,
    autofit_columns,
    reset_row_heights,
)
from .pdf_render import (
    convert_libreoffice,
    find_libreoffice,
    rasterize_pdf_to_tiff,
)

__all__ = [
    "apply_print_preflight",
    "autofit_columns",
    "reset_row_heights",
    "convert_libreoffice",
    "find_libreoffice",
    "rasterize_pdf_to_tiff",
]
