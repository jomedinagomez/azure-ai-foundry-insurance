"""Generate PDF SOV variants 4 (Summit native) and 5 (Heartland scanned-style)."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from PIL import Image, ImageFilter

from seed_data import SUMMIT, HEARTLAND, ROOT, Account

ATTACH_DIR = ROOT / "attachments"
TMP_DIR = ROOT / "scripts" / ".tmp"


# --------------------------------------------------------------------------- #
# Shared content builder — produces the same logical SOV used by both PDFs
# --------------------------------------------------------------------------- #

def _hex_color(h: str) -> colors.Color:
    h = h.lstrip("#")
    return colors.Color(int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


def _build_story(acc: Account, footnote_keys: dict[int, str] | None = None):
    """Build a flowable story (header block + locations table + footnotes)."""
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], textColor=colors.white,
                                  alignment=1, fontSize=14, leading=18)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, spaceAfter=6)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=8.5, leading=10)
    note = ParagraphStyle("Note", parent=styles["Normal"], fontSize=7.5, textColor=colors.gray, leading=9)

    color = _hex_color(acc.broker.color)
    story = []

    # Title bar
    title_tbl = Table([[Paragraph(f"STATEMENT OF VALUES — {acc.insured_name}", title_style)]],
                      colWidths=[10.0 * inch])
    title_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(title_tbl)
    story.append(Spacer(1, 0.15 * inch))

    # Header block (label/value)
    pairs = [
        ("Named Insured",       acc.insured_name),
        ("DBA",                 acc.dba or ""),
        ("Mailing Address",     acc.mailing_address),
        ("Effective Date",      acc.effective_date),
        ("Policy Period",       f"{acc.effective_date} to {acc.expiration_date}"),
        ("Currency",            acc.currency),
        ("Valuation Date",      acc.valuation_date),
        ("Primary Operations",  acc.primary_operations),
        ("NAICS",               acc.naics or ""),
        ("Total Insured Value", f"${sum(l.tiv for l in acc.locations):,.0f}"),
        ("Location Count",      str(len(acc.locations))),
        ("Broker",              acc.broker.name),
        ("Producer Contact",    f"{acc.broker.contact} | {acc.broker.email} | {acc.broker.phone}"),
        ("Prepared By / Date",  f"{acc.prepared_by} — {acc.prepared_date}"),
    ]
    hdr_data = [[Paragraph(f"<b>{k}</b>", body), Paragraph(str(v), body)] for k, v in pairs]
    hdr_tbl = Table(hdr_data, colWidths=[1.7 * inch, 8.3 * inch])
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEEEEE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 0.18 * inch))

    # Schedule of locations
    story.append(Paragraph("SCHEDULE OF LOCATIONS", h2))

    headers = ["Loc", "Address", "City", "ST", "Construction",
               "Occupancy / Operations", "Year", "Sq Ft",
               "Bldg $", "BPP $", "BI/EE $", "Notes"]
    data = [[Paragraph(f"<b>{h}</b>", body) for h in headers]]
    footnote_keys = footnote_keys or {}

    for loc in acc.locations:
        operations = loc.operations_description or loc.occupancy or ""
        if loc.location_number in footnote_keys:
            operations = f"{operations} <super>({footnote_keys[loc.location_number]})</super>"
        notes = loc.notes or ""
        if loc.location_number in footnote_keys:
            notes = f"{notes} <super>({footnote_keys[loc.location_number]})</super>"

        row = [
            str(loc.location_number),
            loc.street,
            loc.city,
            loc.state,
            loc.construction_type or "",
            Paragraph(operations, body),
            str(loc.year_built or ""),
            f"{loc.square_footage:,}" if loc.square_footage else "",
            f"${loc.building_value:,.0f}" if loc.building_value else "",
            f"${loc.bpp_value:,.0f}" if loc.bpp_value else "",
            f"${loc.bi_ee_value:,.0f}" if loc.bi_ee_value else "",
            Paragraph(notes, body),
        ]
        data.append(row)

    col_widths = [0.35, 1.7, 1.0, 0.3, 1.1, 1.9, 0.4, 0.55, 0.75, 0.7, 0.7, 1.05]
    col_widths = [w * inch for w in col_widths]
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(tbl)
    return story


# --------------------------------------------------------------------------- #
# Variant 4: Summit — native PDF with footnotes
# --------------------------------------------------------------------------- #

def build_summit(acc: Account) -> Path:
    out = ATTACH_DIR / "04_summit_SOV.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)

    footnotes = {8: "1", 11: "2"}
    footnote_text = [
        ("1", "Location 8 includes a 25-lane indoor firearms range and gunsmith services. "
              "Range is constructed with reinforced ballistic panels per NRA Range Source Book guidelines."),
        ("2", "Location 11 (Bozeman, MT) is currently under renovation through Q3 2026. "
              "Reported building value reflects post-completion replacement cost basis."),
    ]

    doc = SimpleDocTemplate(str(out), pagesize=landscape(LETTER),
                            leftMargin=0.3 * inch, rightMargin=0.3 * inch,
                            topMargin=0.3 * inch, bottomMargin=0.4 * inch)
    story = _build_story(acc, footnote_keys=footnotes)

    styles = getSampleStyleSheet()
    note_style = ParagraphStyle("Note", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#555555"), leading=10)

    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("<b>FOOTNOTES</b>", note_style))
    for num, text in footnote_text:
        story.append(Paragraph(f"<super>{num}</super> {text}", note_style))

    doc.build(story)
    return out


# --------------------------------------------------------------------------- #
# Variant 5: Heartland — scanned-style PDF (rendered → image → re-PDF, with skew)
# --------------------------------------------------------------------------- #

def build_heartland(acc: Account) -> Path:
    """Render the SOV as a normal PDF, rasterize to image, blur+rotate to simulate a scan, then re-embed as PDF."""
    out = ATTACH_DIR / "05_heartland_SOV.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Build the clean PDF first
    clean_pdf = TMP_DIR / "heartland_clean.pdf"
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(clean_pdf), pagesize=landscape(LETTER),
                            leftMargin=0.3 * inch, rightMargin=0.3 * inch,
                            topMargin=0.3 * inch, bottomMargin=0.4 * inch)
    story = _build_story(acc)

    # Add margin annotation (the seeded anomaly note)
    styles = getSampleStyleSheet()
    note_style = ParagraphStyle("Note", parent=styles["Normal"], fontSize=9,
                                textColor=colors.HexColor("#8B0000"), leading=11)
    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph(
        '<b>HANDWRITTEN MARGIN NOTE (Loc 9):</b> "New silo addition Q4 2026 — '
        'values to be updated at renewal."', note_style))
    doc.build(story)

    # 2. Rasterize to image. Without poppler we use a simple synthetic page render:
    #    we'll create a single image directly via reportlab's canvas → bitmap by drawing
    #    text again onto a PIL image at lower fidelity. Simpler: just build a synthetic
    #    "scanned" image that contains the same SOV content rendered with PIL, then re-PDF it.
    # To keep this self-contained (no poppler/pdf2image), we render a "scanned look" PNG
    # by drawing a simple representation of the SOV onto a tilted, slightly noisy image.
    scan_img = _render_scanned_image(acc)

    # 3. Convert image to PDF
    import img2pdf
    with open(out, "wb") as f:
        f.write(img2pdf.convert(str(scan_img)))

    return out


def _render_scanned_image(acc: Account) -> Path:
    """Render a single-page scanned-look image of the SOV."""
    from PIL import ImageDraw, ImageFont

    W, H = 2200, 1700  # ~landscape letter at ~200 dpi
    bg = (252, 250, 244)  # slightly off-white "paper"
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    def font(size: int) -> ImageFont.FreeTypeFont:
        for path in (r"C:\Windows\Fonts\timesbd.ttf", r"C:\Windows\Fonts\arialbd.ttf"):
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    def font_r(size: int) -> ImageFont.FreeTypeFont:
        for path in (r"C:\Windows\Fonts\times.ttf", r"C:\Windows\Fonts\arial.ttf"):
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    # Title bar
    color = acc.broker.color.lstrip("#")
    rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
    draw.rectangle([(60, 60), (W - 60, 130)], fill=rgb)
    draw.text((90, 78), f"STATEMENT OF VALUES — {acc.insured_name}", fill="white", font=font(28))

    # Header block
    y = 160
    label_font = font(16)
    value_font = font_r(16)
    pairs = [
        ("Named Insured",       acc.insured_name),
        ("Mailing Address",     acc.mailing_address),
        ("Effective Date",      acc.effective_date),
        ("Currency",            acc.currency),
        ("Valuation Date",      acc.valuation_date),
        ("Primary Operations",  acc.primary_operations[:110] + "..."),
        ("Total Insured Value", f"${sum(l.tiv for l in acc.locations):,.0f}"),
        ("Location Count",      str(len(acc.locations))),
        ("Broker",              f"{acc.broker.name}  |  {acc.broker.contact}  |  {acc.broker.email}  |  {acc.broker.phone}"),
        ("Prepared",            f"{acc.prepared_by} — {acc.prepared_date}"),
    ]
    for label, value in pairs:
        draw.text((90, y), f"{label}:", fill="black", font=label_font)
        draw.text((350, y), value, fill="black", font=value_font)
        y += 26

    # Schedule header
    y += 20
    draw.rectangle([(60, y), (W - 60, y + 38)], fill=rgb)
    draw.text((90, y + 8), "SCHEDULE OF LOCATIONS", fill="white", font=font(20))
    y += 46

    headers = ["Loc", "Address", "City", "ST", "ZIP", "Construction", "Occupancy", "Year", "Sq Ft", "Bldg $", "BPP $", "BI/EE $"]
    col_x =   [70,    150,        500,    660,  710,   790,            1020,        1230,   1310,    1430,     1620,    1820]
    col_w =   [78,    340,        160,    50,   80,    220,            210,         70,     110,     180,      180,     220]

    h_font = font(13)
    for x, h in zip(col_x, headers):
        draw.text((x + 4, y + 4), h, fill="black", font=h_font)
    draw.line([(60, y + 26), (W - 60, y + 26)], fill="black", width=2)
    y += 32

    cell_font = font_r(12)
    for loc in acc.locations:
        values = [
            str(loc.location_number),
            loc.street,
            loc.city,
            loc.state,
            loc.zip or "—",
            loc.construction_type or "",
            loc.occupancy or "",
            str(loc.year_built or "—"),
            f"{loc.square_footage:,}" if loc.square_footage else "",
            f"${loc.building_value:,.0f}" if loc.building_value else "",
            f"${loc.bpp_value:,.0f}" if loc.bpp_value else "",
            f"${loc.bi_ee_value:,.0f}" if loc.bi_ee_value else "",
        ]
        for x, v in zip(col_x, values):
            draw.text((x + 4, y + 2), v, fill="black", font=cell_font)
        draw.line([(60, y + 22), (W - 60, y + 22)], fill=(180, 180, 180), width=1)
        y += 28

    # Handwritten-style margin annotation
    y += 14
    annot_font = font(15)
    draw.text((90, y), 'HANDWRITTEN MARGIN NOTE (Loc 9): "New silo addition Q4 2026 — values to be updated at renewal."',
              fill=(140, 0, 0), font=annot_font)

    # ---- Apply scan effects: slight rotate, blur, paper noise ----
    img = img.rotate(-0.6, resample=Image.BICUBIC, fillcolor=bg)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))

    # Save as JPEG to simulate scan compression
    out = TMP_DIR / "heartland_scanned.jpg"
    img.convert("RGB").save(out, "JPEG", quality=78)
    return out


# --------------------------------------------------------------------------- #

def main() -> None:
    print("Generating PDF SOV variants...")
    out1 = build_summit(SUMMIT)
    print(f"  wrote {out1.relative_to(ROOT)}")
    out2 = build_heartland(HEARTLAND)
    print(f"  wrote {out2.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
