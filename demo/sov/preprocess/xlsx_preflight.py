"""xlsx page-setup preflight for clean PDF rendering.

The `apply_print_preflight` function mutates an xlsx so that any downstream
PDF engine (LibreOffice, Excel, Aspose) produces a 1-page-wide layout that
preserves anchored images and uses column widths sized to fit every value.

This is the single most important variable in the xlsx→PDF pipeline. Without
it, default Excel print rendering wraps wide schedules across many pages with
mid-row column breaks — and the rendered PDF is unreadable for both humans
and CU's layout analyzer.

See [research_xlsx_to_pdf.ipynb](../../feedback/underwriting/research_xlsx_to_pdf.ipynb)
for the matrix that established these defaults.
"""
from __future__ import annotations

import math
from pathlib import Path

_EMU_PER_PX = 9525           # English Metric Unit constant
_DEFAULT_ROW_PX = 20          # ~15pt
_DEFAULT_COL_PX = 64          # ~8.43 char width @ Calibri 11pt


def _image_extent_cells(image) -> tuple[int | None, int | None]:
    """Approximate the (end_row_1based, end_col_1based) extent of an anchored
    image so we can extend the print area to cover it.

    Without this, `ws.max_row`/`ws.max_column` only count cell-grid content
    and anchored images get cropped off the printout. The Acme SOV has an
    "ADDITIONAL LOCATIONS" image at row 45 that holds 3 extra rows of the
    schedule; this function ensures it survives the conversion.
    """
    anc = image.anchor
    try:
        from_col = anc._from.col + 1
        from_row = anc._from.row + 1
    except Exception:
        return (None, None)
    cx = cy = None
    ext = getattr(anc, "ext", None)
    if ext is not None and getattr(ext, "cx", None) and getattr(ext, "cy", None):
        cx, cy = ext.cx, ext.cy
    to = getattr(anc, "to", None)
    if to is not None:
        try:
            return (to.row + 1, to.col + 1)
        except Exception:
            pass
    if cx and cy:
        cols = max(1, math.ceil(cx / _EMU_PER_PX / _DEFAULT_COL_PX))
        rows = max(1, math.ceil(cy / _EMU_PER_PX / _DEFAULT_ROW_PX))
        return (from_row + rows, from_col + cols)
    return (from_row + 10, from_col + 5)


def _measure_cell_text(value) -> int:
    if value is None:
        return 0
    s = str(value)
    return max((len(line) for line in s.splitlines()), default=0)


def autofit_columns(
    ws,
    *,
    min_width: float = 6.0,
    max_width: float = 60.0,
    padding: float = 1.2,
) -> None:
    """Approximate Excel's 'AutoFit Column Width', honoring merged-cell ranges.

    openpyxl can't measure font metrics, but `len(str(value))` is a workable
    proxy for proportional fonts at 10-11pt. Merged ranges (e.g. a header
    spanning A:D) distribute their width across the merged columns so one
    long header doesn't force a single column to be huge.
    """
    from openpyxl.utils import get_column_letter

    merged_lookup: dict[tuple[int, int], tuple[int, int]] = {}
    for mr in ws.merged_cells.ranges:
        for r in range(mr.min_row, mr.max_row + 1):
            for c in range(mr.min_col, mr.max_col + 1):
                merged_lookup[(r, c)] = (mr.min_col, mr.max_col)

    col_max: dict[int, float] = {}
    last_row = ws.max_row or 1
    for row_cells in ws.iter_rows(min_row=1, max_row=last_row, values_only=False):
        for cell in row_cells:
            v = cell.value
            if v in (None, ""):
                continue
            text_w = _measure_cell_text(v)
            if not text_w:
                continue
            r, c = cell.row, cell.column
            if (r, c) in merged_lookup:
                cmin, cmax = merged_lookup[(r, c)]
                span = cmax - cmin + 1
                share = max(1.0, text_w / span)
                for cc in range(cmin, cmax + 1):
                    col_max[cc] = max(col_max.get(cc, 0), share)
            else:
                col_max[c] = max(col_max.get(c, 0), text_w)

    for col_idx, width in col_max.items():
        new_w = max(min_width, min(max_width, width * padding + 1))
        ws.column_dimensions[get_column_letter(col_idx)].width = new_w


def reset_row_heights(ws) -> None:
    """Drop explicit row heights so the renderer uses defaults."""
    for rd in ws.row_dimensions.values():
        rd.height = None


def apply_print_preflight(
    xlsx_path: str | Path,
    out_path: str | Path | None = None,
    *,
    autofit: bool = True,
    print_gridlines: bool = False,
) -> Path:
    """Mutate the workbook's page-setup so any PDF engine produces a
    1-page-wide layout that includes anchored images and has columns wide
    enough to show every value.

    Returns the path to the new preflighted xlsx (the input is never mutated).

    `print_gridlines=False` (default) reproduces Excel's natural print output:
    only the borders the workbook itself defines are visible. Set to True if
    you want Excel's standard light gridlines printed everywhere.
    """
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.page import PageMargins

    xlsx_path = Path(xlsx_path)
    out_path = (
        Path(out_path)
        if out_path is not None
        else xlsx_path.with_name(xlsx_path.stem + ".print-ready.xlsx")
    )

    wb = load_workbook(xlsx_path)
    for ws in wb.worksheets:
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
        ws.page_setup.paperSize = ws.PAPERSIZE_LETTER

        ws.print_options.gridLines = print_gridlines
        ws.print_options.gridLinesSet = print_gridlines

        if autofit:
            autofit_columns(ws)
            reset_row_heights(ws)

        last_row = ws.max_row or 1
        last_col = ws.max_column or 1
        for im in list(ws._images):
            er, ec = _image_extent_cells(im)
            if er:
                last_row = max(last_row, er)
            if ec:
                last_col = max(last_col, ec)
        ws.print_area = f"A1:{get_column_letter(last_col)}{last_row}"

        ws.page_margins = PageMargins(
            left=0.3, right=0.3, top=0.3, bottom=0.3, header=0.2, footer=0.2
        )
        ws.print_title_rows = "1:1"

    wb.save(out_path)
    return out_path
