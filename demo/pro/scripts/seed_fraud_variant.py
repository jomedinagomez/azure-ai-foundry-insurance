"""Generate a tampered repair estimate PDF for the fraud-detection demo.

Renders a realistic body-shop estimate document with three deliberate
inconsistencies vs. the policy + the v2 claim form:

1. **TOTALS_EXCEED_SUBLIMIT** -- grand total ($18,940.00) exceeds the
   policy's $12,000 collision sub-limit.
2. **DATE_IMPLAUSIBLE** -- estimate date precedes the date of loss
   (estimate dated five days before the FNOL date-of-loss).
3. **VIN_MISMATCH** -- a single-character typo on the VIN vs. the policy
   declarations.

Run from repo root:

    python demo/pro/scripts/seed_fraud_variant.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# Tampered facts -- carefully chosen mismatches against the reference
# policy (Lexus RX, VIN ...192847, plate BTI4462). Date of loss matches
# what the FNOL will report; estimate is dated 5 days earlier.
ESTIMATE_FACTS = {
    "shop_name": "Anytown Auto Body & Collision",
    "shop_address": "318 Industrial Parkway, Springfield, IL 62701",
    "shop_phone": "(217) 555-0177",
    "shop_license": "IL-ABRA-44719",
    "estimate_number": "EST-2026-04-0998",
    "estimate_date": "2026-03-09",          # BEFORE date_of_loss below
    "date_of_loss_assumed": "2026-03-14",   # what FNOL will report
    "customer_name": "Sarah J. Whitfield",
    "vehicle": "2019 Lexus RX 350 AWD",
    "vin_tampered": "2T2BZMCA5KC192947",    # policy VIN is ...192847 (one char off)
    "license_plate": "BTI4462",
    "mileage": "58,420",
    "policy_number": "PA-7421-2026",
}

LINE_ITEMS = [
    # description, qty, unit_price, total -- driver-side T-bone scope, inflated
    ("Driver-side front door shell (OEM) -- remove & replace", 1, 2150.00, 2150.00),
    ("Driver-side front fender (OEM) -- replace", 1, 1480.00, 1480.00),
    ("Driver-side rear door shell (OEM) -- replace (claimed)", 1, 1820.00, 1820.00),
    ("Driver-side front window glass -- replace", 1, 845.00, 845.00),
    ("Driver-side rear window glass -- replace (claimed)", 1, 720.00, 720.00),
    ("Driver-side door trim, weatherstrip, panels", 1, 985.00, 985.00),
    ("Driver-side mirror assembly -- replace", 1, 680.00, 680.00),
    ("Driver-side A-pillar -- section repair & reinforcement", 1, 1620.00, 1620.00),
    ("Driver-side B-pillar -- section repair (claimed structural)", 1, 2480.00, 2480.00),
    ("Driver-side rocker panel -- straighten and reinforce", 1, 1150.00, 1150.00),
    ("Door wiring harness assembly (full L-side)", 1, 615.00, 615.00),
    ("Wheel alignment & suspension inspection", 1, 295.00, 295.00),
    ("Paint & materials (full driver side, blend roof + quarter)", 1, 1950.00, 1950.00),
    ("Body labor (estimated 38 hrs @ $95/hr)", 38, 95.00, 3610.00),
    # subtotal computes to ~$23,395 before discount; we show $18,940 net of
    # a cosmetic "loyalty discount" to make the number look more plausible.
]

DISCOUNT = -4455.00
TAX_RATE = 0.0
GRAND_TOTAL = sum(t for _, _, _, t in LINE_ITEMS) + DISCOUNT  # = 18940.00

DEST = (
    Path(__file__).resolve().parent.parent
    / "samples"
    / "claim_auto_collision_fraud"
    / "repair_estimate.pdf"
)


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="ShopName", parent=s["Heading1"], textColor=colors.HexColor("#7c2d12"), fontSize=18, spaceAfter=2))
    s.add(ParagraphStyle(name="ShopMeta", parent=s["BodyText"], fontSize=9, textColor=colors.HexColor("#475569")))
    s.add(ParagraphStyle(name="H2Shop", parent=s["Heading2"], textColor=colors.HexColor("#7c2d12"), fontSize=12, spaceAfter=4))
    s.add(ParagraphStyle(name="Small", parent=s["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#475569")))
    return s


def _customer_table(f: dict) -> Table:
    rows = [
        ["Customer:", f["customer_name"], "Estimate #:", f["estimate_number"]],
        ["Vehicle:", f["vehicle"], "Estimate date:", f["estimate_date"]],
        ["VIN:", f["vin_tampered"], "Date of loss:", f["date_of_loss_assumed"]],
        ["License plate:", f["license_plate"], "Mileage:", f["mileage"]],
        ["Policy #:", f["policy_number"], "Insurer ref:", "—"],
    ]
    t = Table(rows, colWidths=[1.1 * inch, 2.6 * inch, 1.1 * inch, 1.9 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#7c2d12")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#7c2d12")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    return t


def _line_items_table() -> Table:
    rows = [["Description", "Qty", "Unit price", "Line total"]]
    for desc, qty, unit, total in LINE_ITEMS:
        rows.append([desc, str(qty), f"${unit:,.2f}", f"${total:,.2f}"])
    rows.append(["Subtotal", "", "", f"${sum(t for _, _, _, t in LINE_ITEMS):,.2f}"])
    rows.append(["Loyalty discount", "", "", f"${DISCOUNT:,.2f}"])
    rows.append(["Tax", "", "", "$0.00"])
    rows.append(["GRAND TOTAL", "", "", f"${GRAND_TOTAL:,.2f}"])
    t = Table(rows, colWidths=[4.3 * inch, 0.5 * inch, 1.05 * inch, 1.05 * inch])
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c2d12")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fef2f2")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ])
    # Highlight grand total
    last = len(rows) - 1
    style.add("FONTNAME", (0, last), (-1, last), "Helvetica-Bold")
    style.add("FONTSIZE", (0, last), (-1, last), 11)
    style.add("BACKGROUND", (0, last), (-1, last), colors.HexColor("#fee2e2"))
    style.add("LINEABOVE", (0, last), (-1, last), 1.0, colors.HexColor("#7c2d12"))
    t.setStyle(style)
    return t


def build(dest: Path = DEST) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dest),
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title="Repair Estimate",
        author=ESTIMATE_FACTS["shop_name"],
    )
    s = _styles()
    f = ESTIMATE_FACTS
    story = []

    story.append(Paragraph(f["shop_name"], s["ShopName"]))
    story.append(Paragraph(
        f"{f['shop_address']} &nbsp;|&nbsp; {f['shop_phone']} &nbsp;|&nbsp; License {f['shop_license']}",
        s["ShopMeta"],
    ))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("REPAIR ESTIMATE", s["H2Shop"]))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_customer_table(f))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Itemized parts and labor", s["H2Shop"]))
    story.append(_line_items_table())
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph(
        "Estimate is valid for 30 days from the date shown above. Supplements may be "
        "issued upon teardown if additional structural damage is found. Customer "
        "authorizes the shop to commence work upon insurer approval; storage fees of "
        "$45 per day apply after settlement is finalized.",
        s["Small"],
    ))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Prepared by: M. Castillo, Estimator (ASE-certified)", s["Small"]))
    story.append(Paragraph(f"Signature on file. Estimate #{f['estimate_number']}.", s["Small"]))

    doc.build(story)
    return dest


def main() -> int:
    out = build()
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
    print(f"  Grand total : ${GRAND_TOTAL:,.2f}  (exceeds policy collision sub-limit)")
    print(f"  Estimate date: {ESTIMATE_FACTS['estimate_date']}  (before date of loss {ESTIMATE_FACTS['date_of_loss_assumed']})")
    print(f"  VIN          : {ESTIMATE_FACTS['vin_tampered']}  (policy VIN ends ...192847)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
