"""Generate a realistic CLEAN repair estimate PDF (no fraud signals).

Total stays under the policy collision sub-limit, dates are after the
date of loss, and the VIN matches the policy. This is the body-shop
estimate used by the `claim_auto_collision` (clean) sample.

Run from repo root:

    python demo/pro/scripts/generate_clean_estimate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_policy import POLICY_FACTS  # noqa: E402
from generate_claim_form import FNOL_FACTS  # noqa: E402

ESTIMATE_FACTS = {
    "shop_name": "Anytown Auto Body & Collision",
    "shop_address": "318 Industrial Parkway, Springfield, IL 62701",
    "shop_phone": "(217) 555-0177",
    "shop_license": "IL-ABRA-44719",
    "estimate_number": "EST-2026-03-1071",
    "estimate_date": "2026-03-16",  # 2 days AFTER date of loss
    "date_of_loss_assumed": FNOL_FACTS["date_of_loss"],
    "customer_name": POLICY_FACTS["named_insured"],
    "vehicle": POLICY_FACTS["vehicle"],
    "vin": POLICY_FACTS["vin"],  # matches policy
    "license_plate": POLICY_FACTS["license_plate"],
    "mileage": "58,420",
    "policy_number": POLICY_FACTS["policy_number"],
    "estimator": "K. Patel, Estimator (ASE-certified)",
}

LINE_ITEMS = [
    ("Driver-side front door shell (OEM) -- remove & replace", 1, 1480.00, 1480.00),
    ("Driver-side front fender (OEM) -- replace", 1, 980.00, 980.00),
    ("Driver-side front window glass -- replace", 1, 545.00, 545.00),
    ("Driver-side door trim & weatherstrip kit", 1, 285.00, 285.00),
    ("Driver-side mirror assembly (power, heated) -- replace", 1, 420.00, 420.00),
    ("Driver-side A-pillar trim -- replace", 1, 165.00, 165.00),
    ("Door wiring harness -- inspect & repair", 1, 240.00, 240.00),
    ("Glass cleanup / vacuum interior (driver-side foot-well)", 1, 95.00, 95.00),
    ("Wheel alignment check -- 4-wheel", 1, 195.00, 195.00),
    ("Paint & materials (door + fender, blend rear quarter)", 1, 780.00, 780.00),
    ("Body labor (estimated 22 hrs @ $95/hr)", 22, 95.00, 2090.00),
    ("Detailing & post-repair inspection", 1, 165.00, 165.00),
]

DISCOUNT = 0.0
GRAND_TOTAL = sum(t for _, _, _, t in LINE_ITEMS) + DISCOUNT  # = $7,440.00 (< $12,000 sub-limit)

DEST = Path(__file__).resolve().parent.parent / "source-data" / "generated" / "repair_estimate.pdf"


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="ShopName", parent=s["Heading1"], textColor=colors.HexColor("#0f766e"),
                         fontSize=18, spaceAfter=2))
    s.add(ParagraphStyle(name="ShopMeta", parent=s["BodyText"], fontSize=9,
                         textColor=colors.HexColor("#475569")))
    s.add(ParagraphStyle(name="H2Shop", parent=s["Heading2"], textColor=colors.HexColor("#0f766e"),
                         fontSize=12, spaceAfter=4))
    s.add(ParagraphStyle(name="Small", parent=s["BodyText"], fontSize=8, leading=10,
                         textColor=colors.HexColor("#475569")))
    return s


def _customer_table(f) -> Table:
    rows = [
        ["Customer:", f["customer_name"], "Estimate #:", f["estimate_number"]],
        ["Vehicle:", f["vehicle"], "Estimate date:", f["estimate_date"]],
        ["VIN:", f["vin"], "Date of loss:", f["date_of_loss_assumed"]],
        ["License plate:", f["license_plate"], "Mileage:", f["mileage"]],
        ["Policy #:", f["policy_number"], "Insurer ref:", "—"],
    ]
    t = Table(rows, colWidths=[1.1 * inch, 2.6 * inch, 1.1 * inch, 1.9 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#0f766e")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    return t


def _line_items_table() -> Table:
    rows = [["Description", "Qty", "Unit price", "Line total"]]
    for desc, qty, unit, total in LINE_ITEMS:
        rows.append([desc, str(qty), f"${unit:,.2f}", f"${total:,.2f}"])
    rows.append(["Subtotal", "", "", f"${sum(t for _, _, _, t in LINE_ITEMS):,.2f}"])
    rows.append(["Tax", "", "", "$0.00"])
    rows.append(["GRAND TOTAL", "", "", f"${GRAND_TOTAL:,.2f}"])
    t = Table(rows, colWidths=[4.3 * inch, 0.5 * inch, 1.05 * inch, 1.05 * inch])
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecfdf5")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    last = len(rows) - 1
    style.add("FONTNAME", (0, last), (-1, last), "Helvetica-Bold")
    style.add("FONTSIZE", (0, last), (-1, last), 11)
    style.add("BACKGROUND", (0, last), (-1, last), colors.HexColor("#d1fae5"))
    t.setStyle(style)
    return t


def build(dest: Path = DEST) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dest), pagesize=LETTER,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
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
    story.append(_customer_table(f))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Itemized parts and labor", s["H2Shop"]))
    story.append(_line_items_table())
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph(
        "Estimate is valid for 30 days from the date shown above. Supplements may be issued "
        "upon teardown if additional damage is found.",
        s["Small"],
    ))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(f"Prepared by: {f['estimator']}", s["Small"]))
    story.append(Paragraph(f"Signature on file. Estimate #{f['estimate_number']}.", s["Small"]))

    doc.build(story)
    return dest


def main() -> int:
    out = build()
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
    print(f"  Grand total : ${GRAND_TOTAL:,.2f}  (within policy sub-limit ${POLICY_FACTS['limit_collision_sublimit']:,})")
    print(f"  Estimate date: {ESTIMATE_FACTS['estimate_date']}  (after date of loss {ESTIMATE_FACTS['date_of_loss_assumed']})")
    print(f"  VIN          : {ESTIMATE_FACTS['vin']}  (matches policy)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
