"""Generate a realistic synthetic police accident report PDF.

Cross-document facts (VIN, date of loss, location, claimant name) match
the FNOL claim form so the 'clean' scenario stays consistent.

Run from repo root:

    python demo/pro/scripts/generate_police_report.py
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

REPORT_FACTS = {
    "agency": "Springfield Police Department",
    "agency_addr": "800 East Monroe Street, Springfield, IL 62701",
    "report_no": FNOL_FACTS["police_report_number"],
    "report_date": FNOL_FACTS["date_of_loss"],
    "incident_date": FNOL_FACTS["date_of_loss"],
    "incident_time": FNOL_FACTS["time_of_loss"],
    "responding_officer": "Officer J. Ramirez, Badge #4471",
    "supervisor": "Sgt. K. Thompson",
    "weather": "Clear, 41°F, dry pavement",
    "light": "Daylight",
    "location": FNOL_FACTS["loss_location"],
    "summary": (
        "On 2026-03-14 at approximately 07:42 hours, responding officer was "
        "dispatched to a two-vehicle side-impact collision at the intersection "
        "of Maple Grove Drive and 4th Avenue in Springfield, IL. Upon arrival, "
        "Vehicle 1 was stopped on the east side of the intersection with "
        "significant damage to the entire DRIVER SIDE (front door, fender, "
        "window glass, side mirror). Vehicle 2 was stopped approximately 20 "
        "feet north of the intersection with front-bumper and grille damage."
    ),
    "narrative": (
        "Driver of Vehicle 1 (Whitfield) stated she was traveling westbound on "
        "Maple Grove Drive with a green light when Vehicle 2 (Hernandez) "
        "entered the intersection northbound on 4th Avenue without stopping. "
        "Vehicle 2 struck the DRIVER-SIDE front door and fender of Vehicle 1 "
        "at an estimated 30 MPH. Driver of Vehicle 2 admitted he believed the "
        "signal was yellow and accelerated to clear the intersection. Northbound "
        "signal phase confirmed RED at time of collision via intersection "
        "signal log. Driver-side window of Vehicle 1 shattered on impact; glass "
        "fragments observed throughout driver-side foot-well. No injuries "
        "reported by either driver; both refused medical transport. Vehicle 1 "
        "sustained damage to driver-side front door, driver-side fender, "
        "driver-side window, A-pillar trim, and driver-side mirror. Vehicle 2 "
        "sustained damage to front bumper cover, grille, and right front "
        "headlight. Both vehicles remained drivable. No tow required."
    ),
    "v1_name": POLICY_FACTS["named_insured"],
    "v1_dl": "IL-W632-4421-1487",
    "v1_vehicle": POLICY_FACTS["vehicle"],
    "v1_vin": POLICY_FACTS["vin"],
    "v1_plate": POLICY_FACTS["license_plate"],
    "v1_insurer": POLICY_FACTS["carrier"],
    "v1_policy": POLICY_FACTS["policy_number"],
    "v2_name": FNOL_FACTS["other_driver_name"],
    "v2_dl": "IL-H218-9941-2206",
    "v2_vehicle": "2019 Ford F-150 XL Crew Cab",
    "v2_vin": "1FTEW1EP4KFA28110",
    "v2_plate": "IL HG7-2208",
    "v2_insurer": FNOL_FACTS["other_driver_insurer"],
    "v2_policy": FNOL_FACTS["other_driver_policy"],
    "citation": "Citation issued to Driver of Vehicle 2 for disobeying a traffic control signal (625 ILCS 5/11-306).",
    "fault": "Driver of Vehicle 2 (Hernandez) — at fault per officer determination and intersection signal log.",
}

DEST = Path(__file__).resolve().parent.parent / "source-data" / "generated" / "police_report.pdf"


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="AgencyTitle", parent=s["Heading1"],
                         textColor=colors.HexColor("#1e3a8a"), fontSize=16, spaceAfter=2))
    s.add(ParagraphStyle(name="AgencyMeta", parent=s["BodyText"], fontSize=9,
                         textColor=colors.HexColor("#475569"), spaceAfter=6))
    s.add(ParagraphStyle(name="SectionH", parent=s["Heading2"],
                         textColor=colors.HexColor("#1e3a8a"), fontSize=11, spaceBefore=8, spaceAfter=4))
    s.add(ParagraphStyle(name="Body", parent=s["BodyText"], fontSize=10, leading=13))
    s.add(ParagraphStyle(name="Small", parent=s["BodyText"], fontSize=8,
                         leading=10, textColor=colors.HexColor("#475569")))
    return s


def _kv(rows, key_w=1.6, val_w=5.2) -> Table:
    t = Table(rows, colWidths=[key_w * inch, val_w * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1e3a8a")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    return t


def _two_party(headers, v1_rows, v2_rows) -> Table:
    rows = [["", "Vehicle 1", "Vehicle 2"]]
    for label, a, b in zip(headers, v1_rows, v2_rows):
        rows.append([label, a, b])
    t = Table(rows, colWidths=[1.3 * inch, 2.7 * inch, 2.7 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (0, -1), colors.HexColor("#1e3a8a")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def build(dest: Path = DEST) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dest),
        pagesize=LETTER,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title="Traffic Crash Report",
        author=REPORT_FACTS["agency"],
    )
    s = _styles()
    r = REPORT_FACTS
    story = []

    story.append(Paragraph(r["agency"], s["AgencyTitle"]))
    story.append(Paragraph(r["agency_addr"], s["AgencyMeta"]))
    story.append(Paragraph("TRAFFIC CRASH REPORT", s["SectionH"]))
    story.append(_kv([
        ("Report #:", r["report_no"]),
        ("Report date:", r["report_date"]),
        ("Incident date / time:", f"{r['incident_date']} at {r['incident_time']} hrs"),
        ("Responding officer:", r["responding_officer"]),
        ("Reviewing supervisor:", r["supervisor"]),
        ("Weather conditions:", r["weather"]),
        ("Lighting conditions:", r["light"]),
        ("Location:", r["location"]),
    ]))

    story.append(Paragraph("Summary", s["SectionH"]))
    story.append(Paragraph(r["summary"], s["Body"]))

    story.append(Paragraph("Parties", s["SectionH"]))
    story.append(_two_party(
        ["Driver", "Driver License #", "Vehicle", "VIN", "Plate", "Insurer", "Policy #"],
        [r["v1_name"], r["v1_dl"], r["v1_vehicle"], r["v1_vin"], r["v1_plate"], r["v1_insurer"], r["v1_policy"]],
        [r["v2_name"], r["v2_dl"], r["v2_vehicle"], r["v2_vin"], r["v2_plate"], r["v2_insurer"], r["v2_policy"]],
    ))

    story.append(Paragraph("Narrative", s["SectionH"]))
    story.append(Paragraph(r["narrative"], s["Body"]))

    story.append(Paragraph("Determination of Fault", s["SectionH"]))
    story.append(Paragraph(r["fault"], s["Body"]))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(r["citation"], s["Body"]))

    story.append(Paragraph("Diagram of Collision", s["SectionH"]))
    story.append(Paragraph(
        "[ASCII-rendered diagram for demo purposes — actual report would include a hand-drawn diagram.]",
        s["Small"],
    ))
    story.append(Paragraph(
        "<font face='Courier'>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;N<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;|<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;[V2] (northbound, ran red)<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;|<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;v<br/>"
        "&lt;== [V1] (westbound, green) -- impact on driver side<br/>"
        "&nbsp;&nbsp;&nbsp;Maple Grove Dr / 4th Ave"
        "</font>",
        s["Body"],
    ))

    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph("Officer signature: /s/ J. Ramirez, Badge #4471", s["Small"]))
    story.append(Paragraph("Supervisor signature: /s/ K. Thompson, Sgt.", s["Small"]))
    story.append(Paragraph(
        "This report is provided for insurance and civil proceedings. Certified copies "
        "are available upon request from the Springfield Police Records Division.",
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
