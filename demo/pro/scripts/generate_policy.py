"""Generate a realistic synthetic auto insurance policy PDF.

This file is used as the **reference dataset** for the pro-mode analyzers.
Facts (named insured, VIN, policy number, coverage limits) are tuned so a
clean claim package reads as consistent and a tampered one trips both the
CU reasoning and the fraud-rule engine.

Run from repo root:

    python demo/pro/scripts/generate_policy.py
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
    PageBreak,
)

# Canonical facts -- intentionally shared with the manifest.json files so
# the fraud variants can express deliberate mismatches. Vehicle is tuned
# to match the upstream `damage_photo.png` (silver Lexus RX, plate BTI4462).
POLICY_FACTS = {
    "carrier": "Contoso Casualty Insurance Company",
    "policy_number": "PA-7421-2026",
    "named_insured": "Sarah J. Whitfield",
    "address": "742 Maple Grove Drive, Springfield, IL 62704",
    "vin": "2T2BZMCA5KC192847",
    "vehicle": "2019 Lexus RX 350 AWD",
    "license_plate": "BTI4462",
    "policy_effective": "2026-01-15",
    "policy_expiration": "2027-01-15",
    "deductible_collision": 1000,
    "deductible_comprehensive": 500,
    "limit_collision_sublimit": 12000,
    "limit_property_damage_liability": 100000,
    "limit_bodily_injury_per_person": 250000,
    "limit_bodily_injury_per_accident": 500000,
    "limit_uninsured_motorist": 100000,
}

DEST = Path(__file__).resolve().parent.parent / "reference-data" / "auto_policy.pdf"


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="H1Brand", parent=s["Heading1"], textColor=colors.HexColor("#0a3b66"), spaceAfter=8))
    s.add(ParagraphStyle(name="H2Brand", parent=s["Heading2"], textColor=colors.HexColor("#0a3b66"), spaceAfter=4))
    s.add(ParagraphStyle(name="Small", parent=s["BodyText"], fontSize=8, leading=10))
    return s


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    t = Table(rows, colWidths=[2.4 * inch, 4.0 * inch])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#0a3b66")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ]
        )
    )
    return t


def build(dest: Path = DEST) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dest),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Personal Auto Policy Declarations",
        author=POLICY_FACTS["carrier"],
    )
    s = _styles()
    f = POLICY_FACTS
    story = []

    # ── Page 1: Declarations ────────────────────────────────────────────
    story.append(Paragraph(f["carrier"], s["H1Brand"]))
    story.append(Paragraph("Personal Auto Policy — Declarations Page", s["H2Brand"]))
    story.append(Spacer(1, 0.15 * inch))

    story.append(_kv_table([
        ("Policy Number:", f["policy_number"]),
        ("Named Insured:", f["named_insured"]),
        ("Mailing Address:", f["address"]),
        ("Policy Period:", f"{f['policy_effective']} 12:01 a.m. to {f['policy_expiration']} 12:01 a.m."),
        ("Underwriting Office:", "Contoso Casualty — Midwest Region, Chicago, IL"),
    ]))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Insured Vehicle", s["H2Brand"]))
    story.append(_kv_table([
        ("VIN:", f["vin"]),
        ("Year / Make / Model:", f["vehicle"]),
        ("Garaging Address:", f["address"]),
        ("Primary Use:", "Pleasure / commute under 15 miles one-way"),
        ("Annual Mileage:", "9,800 (estimated)"),
    ]))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Coverage Schedule and Limits", s["H2Brand"]))
    cov = [
        ["Coverage", "Limit (USD)", "Deductible (USD)"],
        ["Bodily Injury Liability (per person)", f"${f['limit_bodily_injury_per_person']:,}", "—"],
        ["Bodily Injury Liability (per accident)", f"${f['limit_bodily_injury_per_accident']:,}", "—"],
        ["Property Damage Liability", f"${f['limit_property_damage_liability']:,}", "—"],
        ["Collision", f"${f['limit_collision_sublimit']:,} (sub-limit)", f"${f['deductible_collision']:,}"],
        ["Comprehensive (Other Than Collision)", "Actual cash value", f"${f['deductible_comprehensive']:,}"],
        ["Uninsured / Underinsured Motorist", f"${f['limit_uninsured_motorist']:,}", "—"],
        ["Medical Payments", "$5,000", "—"],
        ["Roadside Assistance", "Included", "—"],
    ]
    t = Table(cov, colWidths=[3.0 * inch, 1.8 * inch, 1.6 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a3b66")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        f"<b>Important — Collision sub-limit.</b> The maximum amount payable for any single collision loss "
        f"to the insured vehicle is <b>${f['limit_collision_sublimit']:,} USD</b>, less the collision deductible "
        f"of <b>${f['deductible_collision']:,} USD</b>. Repair estimates, invoices, and supplements that, in "
        f"aggregate, exceed this sub-limit require written underwriter approval before settlement.",
        s["BodyText"],
    ))

    story.append(PageBreak())

    # ── Page 2: Conditions & Exclusions ─────────────────────────────────
    story.append(Paragraph("Policy Conditions", s["H2Brand"]))
    story.append(Paragraph(
        "1. <b>Notice of loss.</b> The named insured must give prompt notice to the company or its authorized "
        "representative of any accident, occurrence, or loss for which coverage is sought under this policy. "
        "The date of loss recorded on the First Notice of Loss form establishes the start of the claim period; "
        "repair estimates, invoices, or supplements dated <i>prior</i> to the date of loss are presumed to be "
        "for pre-existing damage and are not covered under this policy.",
        s["BodyText"],
    ))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(
        "2. <b>Vehicle identification.</b> All claim documents, including police reports, repair estimates, "
        "and shop invoices, must reference the Vehicle Identification Number (VIN) shown on this Declarations "
        "page. VIN discrepancies will be flagged for special investigation.",
        s["BodyText"],
    ))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(
        "3. <b>Reasonable and necessary repairs.</b> The company will pay only the reasonable and necessary "
        "cost to repair or replace damaged property with material of like kind and quality, subject to the "
        "applicable sub-limit and deductible. Itemized estimates with line-item totals are required.",
        s["BodyText"],
    ))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(
        "4. <b>Required supporting documents.</b> For collision losses with claimed damage in excess of "
        "$2,000, the named insured must submit: (a) a completed First Notice of Loss form, (b) a copy of any "
        "police report filed for the incident, (c) an itemized repair estimate from a licensed body shop, "
        "and (d) photographs of the damaged vehicle. Claims missing any of these documents will be held "
        "open pending receipt.",
        s["BodyText"],
    ))

    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Exclusions", s["H2Brand"]))
    for excl in [
        "Loss arising from use of the insured vehicle for ridesharing, livery, or other for-hire transport.",
        "Loss arising from any operator not listed on this policy and not holding a valid driver's license.",
        "Mechanical or electrical breakdown unrelated to a covered collision or comprehensive event.",
        "Cosmetic damage (e.g. minor scratches and dings) that predates the policy effective date.",
        "Any loss the named insured intentionally caused or in which the named insured participated in fraud.",
    ]:
        story.append(Paragraph(f"• {excl}", s["BodyText"]))
        story.append(Spacer(1, 0.04 * inch))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        f"This policy is issued by {f['carrier']}. Policy form PA-2025-IL. "
        f"In witness whereof, the company has caused this Declarations page to be signed by its authorized representative.",
        s["Small"],
    ))

    doc.build(story)
    return dest


def main() -> int:
    out = build()
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
