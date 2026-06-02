"""Generate a realistic synthetic FNOL (First Notice of Loss) auto claim form.

Facts are wired to match the reference policy (auto_policy.pdf) so the
'clean' scenario reads as consistent end-to-end. The same PDF is used by
both sample bundles (the fraud scenario tampers only the repair estimate).

Run from repo root:

    python demo/pro/scripts/generate_claim_form.py
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

# Date of loss is the day the police report records and the day the
# tampered estimate sits 5 days BEFORE. Garaging address from the policy.
# Loss scenario is a driver-side T-bone collision -- matches the upstream
# damage_photo.png, which shows driver-side door / fender / window damage
# on a silver Lexus RX.
FNOL_FACTS = {
    "claim_number": "CL-2026-03-14-0445",
    "fnol_received": "2026-03-14",
    "date_of_loss": "2026-03-14",
    "time_of_loss": "07:42",
    "loss_location": "Intersection of Maple Grove Dr & 4th Ave, Springfield, IL",
    "loss_type": "Two-vehicle side-impact collision (driver-side T-bone)",
    "claimant_phone": "(217) 555-0149",
    "claimant_email": "sarah.whitfield@example.com",
    "reported_by": "Sarah J. Whitfield (insured)",
    "narrative": (
        "Insured was traveling westbound on Maple Grove Drive and had just "
        "entered the intersection with 4th Avenue on a green light when a "
        "second vehicle (Driver B) traveling northbound on 4th Avenue ran "
        "the red light and struck the DRIVER SIDE of the insured vehicle. "
        "Insured reports significant damage to the driver-side front door, "
        "driver-side fender, driver-side window (shattered), exterior trim, "
        "and side mirror. The driver-side airbag did not deploy. Insured "
        "sustained no injuries but was shaken. Police arrived on scene and "
        "filed report #SPD-2026-04391. Vehicle was driven (with caution) to "
        "Anytown Auto Body for estimate."
    ),
    "police_report_filed": "Yes",
    "police_report_number": "SPD-2026-04391",
    "other_driver_name": "David R. Hernandez",
    "other_driver_insurer": "Premier Mutual Insurance",
    "other_driver_policy": "PM-3318-2025",
    "injuries": "None reported",
    "tow_required": "No (vehicle drivable)",
    "vehicle_drivable": "Yes",
    "estimated_damage_range": "$6,500 – $9,500",
}

DEST = Path(__file__).resolve().parent.parent / "source-data" / "generated" / "claim_form.pdf"


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="FormTitle", parent=s["Heading1"],
                         textColor=colors.HexColor("#0a3b66"), fontSize=16, spaceAfter=4))
    s.add(ParagraphStyle(name="FormSubtitle", parent=s["BodyText"],
                         textColor=colors.HexColor("#475569"), fontSize=10, spaceAfter=8))
    s.add(ParagraphStyle(name="SectionH", parent=s["Heading2"],
                         textColor=colors.HexColor("#0a3b66"), fontSize=11, spaceBefore=8, spaceAfter=4))
    s.add(ParagraphStyle(name="Body", parent=s["BodyText"], fontSize=10, leading=13))
    s.add(ParagraphStyle(name="Small", parent=s["BodyText"], fontSize=8,
                         leading=10, textColor=colors.HexColor("#475569")))
    return s


def _kv(rows: list[tuple[str, str]]) -> Table:
    t = Table(rows, colWidths=[1.6 * inch, 5.2 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0a3b66")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    return t


def _four_col(rows: list[tuple[str, str, str, str]]) -> Table:
    t = Table(rows, colWidths=[1.3 * inch, 2.2 * inch, 1.3 * inch, 2.0 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0a3b66")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#0a3b66")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    return t


def build(dest: Path = DEST) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dest),
        pagesize=LETTER,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title="First Notice of Loss — Auto",
        author=POLICY_FACTS["carrier"],
    )
    s = _styles()
    p, f = POLICY_FACTS, FNOL_FACTS
    story = []

    story.append(Paragraph(p["carrier"], s["FormTitle"]))
    story.append(Paragraph("First Notice of Loss — Personal Auto Claim Form", s["FormSubtitle"]))
    story.append(_four_col([
        ("Claim #:", f["claim_number"], "FNOL received:", f["fnol_received"]),
        ("Reported by:", f["reported_by"], "Channel:", "Phone / Mobile app"),
    ]))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("1. Policyholder", s["SectionH"]))
    story.append(_kv([
        ("Named Insured:", p["named_insured"]),
        ("Policy #:", p["policy_number"]),
        ("Mailing Address:", p["address"]),
        ("Phone:", f["claimant_phone"]),
        ("Email:", f["claimant_email"]),
        ("Policy Period:", f"{p['policy_effective']} to {p['policy_expiration']}"),
    ]))

    story.append(Paragraph("2. Insured Vehicle", s["SectionH"]))
    story.append(_four_col([
        ("VIN:", p["vin"], "Year/Make/Model:", p["vehicle"]),
        ("Plate:", p["license_plate"], "Garaging Address:", p["address"]),
        ("Drivable:", f["vehicle_drivable"], "Tow Required:", f["tow_required"]),
    ]))

    story.append(Paragraph("3. Loss Details", s["SectionH"]))
    story.append(_four_col([
        ("Date of Loss:", f["date_of_loss"], "Time of Loss:", f["time_of_loss"]),
        ("Loss Type:", f["loss_type"], "Injuries:", f["injuries"]),
    ]))
    story.append(_kv([
        ("Loss Location:", f["loss_location"]),
        ("Estimated damage range:", f["estimated_damage_range"]),
    ]))

    story.append(Paragraph("4. Description of Incident", s["SectionH"]))
    story.append(Paragraph(f["narrative"], s["Body"]))

    story.append(Paragraph("5. Other Party Involved", s["SectionH"]))
    story.append(_kv([
        ("Driver Name:", f["other_driver_name"]),
        ("Driver Insurer:", f["other_driver_insurer"]),
        ("Driver Policy #:", f["other_driver_policy"]),
    ]))

    story.append(Paragraph("6. Authorities &amp; Supporting Documents", s["SectionH"]))
    story.append(_kv([
        ("Police report filed:", f["police_report_filed"]),
        ("Police report #:", f["police_report_number"]),
        ("Attached estimate:", "Anytown Auto Body & Collision (forthcoming)"),
        ("Photos attached:", "1 photo, driver-side view of vehicle (file: damage_photo.png)"),
    ]))

    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(
        "I certify that the information provided above is true and complete to the best of my knowledge. "
        "I understand that any person who knowingly and with intent to defraud any insurance company files "
        "a statement of claim containing materially false information may be guilty of insurance fraud.",
        s["Small"],
    ))
    story.append(Spacer(1, 0.15 * inch))
    story.append(_kv([
        ("Signature:", "/s/ Sarah J. Whitfield"),
        ("Date signed:", f["date_of_loss"]),
        ("Adjuster assigned:", "M. Chen, Claims Adjuster (SCA-7821)"),
    ]))

    doc.build(story)
    return dest


def main() -> int:
    out = build()
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
