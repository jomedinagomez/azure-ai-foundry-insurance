"""Generate broker submission .eml files — one per account.

Each .eml has:
  * From: broker (fictional address)
  * To: underwriting intake mailbox
  * Subject: realistic broker subject line
  * Body: HTML with a broker signature including an inline (CID) logo image
  * Attachment: the corresponding SOV file from attachments/
"""
from __future__ import annotations

import mimetypes
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from seed_data import ACCOUNTS, ROOT, Account

EMAIL_DIR = ROOT / "emails"
LOGO_DIR = EMAIL_DIR / "signatures"
ATTACH_DIR = ROOT / "attachments"

UNDERWRITING_INBOX = "cl-property-intake@sov-demo.example.com"


# Body templates per account — each broker has a different writing style
def _body_text(acc: Account, attach_filename: str) -> tuple[str, str]:
    """Return (subject, html_body)."""

    if acc.key == "acme":
        subject = f"NEW SUBMISSION — {acc.insured_name} — Property — Eff {acc.effective_date}"
        opener = (
            f"<p>Hi team,</p>"
            f"<p>Pleased to submit <b>{acc.insured_name}</b> for your consideration. "
            f"This is a new-business property submission with an effective date of "
            f"<b>{acc.effective_date}</b>. The account is a multi-state manufacturer and distributor "
            f"of industrial fasteners with <b>22 locations</b> across 8 states "
            f"(headquartered in Cleveland, OH).</p>"
            f"<p>Total Insured Value comes in at approximately "
            f"<b>${sum(l.tiv for l in acc.locations):,.0f}</b>. The largest single location is the "
            f"main manufacturing plant in Cleveland (~$49M TIV).</p>"
            f"<p>A few notes for your review:</p>"
            f"<ul>"
            f"<li>Locations 11-14 (Cincinnati industrial park) are reported with placeholder "
            f"replacement-cost values pending an updated appraisal — flagging in advance.</li>"
            f"<li>Location 18 (Birmingham, AL) was recently acquired; values may need refinement.</li>"
            f"<li>The SOV embedded image at the bottom of the spreadsheet shows three additional "
            f"locations (20-22) added late in the cycle — please confirm they're picked up.</li>"
            f"</ul>"
            f"<p>Loss runs and the ACORD 140 will follow under separate cover. Happy to schedule a "
            f"call if it's helpful.</p>"
        )

    elif acc.key == "cascade":
        subject = f"Submission: {acc.insured_name} — Property — {acc.effective_date} effective"
        opener = (
            f"<p>Hello,</p>"
            f"<p>Submitting <b>{acc.insured_name}</b> for property quote. Refrigerated and frozen "
            f"warehousing operator across the Pacific Northwest and Northern California — "
            f"<b>{len(acc.locations)} locations</b>, total TIV "
            f"<b>${sum(l.tiv for l in acc.locations):,.0f}</b>.</p>"
            f"<p>Standard cold-storage account; protective systems in place at all locations. "
            f"SOV attached in our usual format.</p>"
        )

    elif acc.key == "magnolia":
        subject = f"{acc.insured_name} — Property Submission — Effective {acc.effective_date}"
        opener = (
            f"<p>Good morning,</p>"
            f"<p>I'm pleased to introduce <b>{acc.insured_name}</b>, a Gulf Coast hospitality "
            f"operator with <b>{len(acc.locations)} locations</b> across LA, MS, FL, GA, and NC "
            f"(boutique hotels and full-service restaurants).</p>"
            f"<p>Total Insured Value is approximately "
            f"<b>${sum(l.tiv for l in acc.locations):,.0f}</b>. The account does carry meaningful "
            f"named-windstorm exposure given the Gulf Coast concentration — please see the "
            f"<i>CAT Exposure</i> tab in the attached workbook for a per-location breakdown.</p>"
            f"<p>Account is well-protected, sprinklered throughout, and the insured maintains "
            f"an active hurricane preparedness program. Looking forward to your indication.</p>"
        )

    elif acc.key == "summit":
        subject = f"New Property Submission — {acc.insured_name} — Effective {acc.effective_date}"
        opener = (
            f"<p>Team —</p>"
            f"<p>Submitting <b>{acc.insured_name}</b>, a regional outdoor recreation retailer "
            f"with <b>{len(acc.locations)} stores</b> across CO, UT, OR, NM, WY, MT, and ID. "
            f"TIV approximately <b>${sum(l.tiv for l in acc.locations):,.0f}</b>.</p>"
            f"<p>Two items to flag:</p>"
            f"<ul>"
            f"<li><b>Location 8 (Colorado Springs)</b> includes a 25-lane indoor firearms range "
            f"and gunsmith services — see footnote 1 in the attached PDF for protective details.</li>"
            f"<li>Location 11 (Bozeman) is currently under renovation; reported value is "
            f"post-completion replacement cost.</li>"
            f"</ul>"
            f"<p>SOV is attached as PDF (insured's preferred format).</p>"
        )

    elif acc.key == "heartland":
        subject = f"Property Submission - {acc.insured_name} - {acc.effective_date}"
        opener = (
            f"<p>Hi,</p>"
            f"<p>Please find attached the property SOV for <b>{acc.insured_name}</b>, an "
            f"agricultural processor operating <b>{len(acc.locations)} facilities</b> across "
            f"the Midwest (corn, soy, grain handling, and animal feed). "
            f"Effective date <b>{acc.effective_date}</b>, TIV approximately "
            f"<b>${sum(l.tiv for l in acc.locations):,.0f}</b>.</p>"
            f"<p>The SOV came to us as a scan from the insured's risk manager. A few cells were "
            f"left blank — I've noted the gaps in the margin where I caught them. Apologies for "
            f"the format; I'll work with the insured to get a cleaner version at renewal.</p>"
        )

    elif acc.key == "coastal":
        subject = f"FW: {acc.insured_name} — Property — eff {acc.effective_date}"
        opener = (
            f"<p>Hi all,</p>"
            f"<p>Forwarding submission for <b>{acc.insured_name}</b>. Marine services operator "
            f"with <b>{len(acc.locations)} locations</b> along the southeastern Atlantic coast "
            f"plus one Canadian operation in Halifax (NS). TIV approximately "
            f"<b>${sum(l.tiv for l in acc.locations):,.0f}</b>.</p>"
            f"<p>Important — the insured's spreadsheet has a few quirks I wanted to flag up front:</p>"
            f"<ul>"
            f"<li>The Halifax location reports <b>values in CAD</b>, not USD — please normalize at "
            f"your prevailing FX.</li>"
            f"<li>Building-value column is labelled inconsistently across the sheet "
            f"(<i>Bldg Val</i> in some rows, <i>RC Bldg</i> in the subtotal block, "
            f"<i>Building Replacement Cost</i> at grand total).</li>"
            f"<li>Significant coastal CAT exposure — every US location is within ~5 mi of coast.</li>"
            f"</ul>"
            f"<p>Let me know what additional info you need.</p>"
        )

    else:
        subject = f"Submission: {acc.insured_name}"
        opener = f"<p>Submission attached for {acc.insured_name}.</p>"

    # Common closing + signature
    sig = _signature_html(acc)
    body = f"""\
<html>
  <body style="font-family: 'Segoe UI', Calibri, Arial, sans-serif; font-size: 11pt; color: #222;">
    {opener}
    <p>Best regards,</p>
    {sig}
  </body>
</html>
"""
    return subject, body


def _signature_html(acc: Account) -> str:
    """HTML signature block with inline CID logo + producer details. The CID is replaced when assembled."""
    return f"""\
    <table cellpadding="0" cellspacing="0" style="font-family: 'Segoe UI', Calibri, Arial, sans-serif; font-size: 10pt; color: #333; border-top: 2px solid {acc.broker.color}; padding-top: 8px; margin-top: 14px;">
      <tr>
        <td style="vertical-align: top; padding-right: 14px;">
          <img src="cid:{{LOGO_CID}}" alt="{acc.broker.name}" width="200" style="display:block;">
        </td>
        <td style="vertical-align: top; border-left: 1px solid #ccc; padding-left: 14px;">
          <div style="font-weight: bold; color: {acc.broker.color}; font-size: 11pt;">{acc.broker.contact}</div>
          <div style="color: #555;">Producer — {acc.broker.name}</div>
          <div style="color: #555; font-style: italic; font-size: 9pt;">{acc.broker.tagline}</div>
          <div style="margin-top: 6px;">
            <span style="color: {acc.broker.color}; font-weight: bold;">E:</span>
            <a href="mailto:{acc.broker.email}" style="color: #333; text-decoration: none;">{acc.broker.email}</a><br>
            <span style="color: {acc.broker.color}; font-weight: bold;">P:</span> {acc.broker.phone}<br>
            <span style="color: {acc.broker.color}; font-weight: bold;">W:</span>
            <a href="https://{acc.broker.domain}" style="color: #333; text-decoration: none;">{acc.broker.domain}</a>
          </div>
        </td>
      </tr>
    </table>
    """


def build_email(idx: int, acc: Account, attachment_path: Path, logo_path: Path) -> Path:
    msg = EmailMessage()

    msg["Subject"], html_template = _body_text(acc, attachment_path.name)
    msg["From"] = f"{acc.broker.contact} <{acc.broker.email}>"
    msg["To"] = UNDERWRITING_INBOX
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=acc.broker.domain)

    # Plain text fallback
    msg.set_content(
        f"Submission for {acc.insured_name}. See HTML version for details. "
        f"SOV is attached as {attachment_path.name}."
    )

    # HTML alternative — force base64 CTE to avoid quoted-printable mid-word
    # soft-line-breaks (=) that some clients (Outlook) mis-render as "=X" with
    # the following letter dropped.
    logo_cid = make_msgid(domain=acc.broker.domain)[1:-1]  # strip <>
    html_body = html_template.replace("{LOGO_CID}", logo_cid)
    msg.add_alternative(html_body, subtype="html", cte="base64")

    # Embed inline logo (related to the HTML part)
    html_part = msg.get_payload()[-1]  # the html alternative
    with open(logo_path, "rb") as f:
        html_part.add_related(
            f.read(), maintype="image", subtype="png",
            cid=f"<{logo_cid}>", filename=logo_path.name,
        )

    # Attach the SOV
    ctype, _ = mimetypes.guess_type(attachment_path.name)
    if ctype is None:
        ctype = "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    with open(attachment_path, "rb") as f:
        msg.add_attachment(
            f.read(), maintype=maintype, subtype=subtype, filename=attachment_path.name,
        )

    out = EMAIL_DIR / f"{idx:02d}_{acc.key}_submission.eml"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(bytes(msg))
    return out


# Map account.key -> attachment filename
ATTACHMENT_MAP = {
    "acme":      "01_acme_SOV.xlsx",
    "cascade":   "02_cascade_SOV.xlsx",
    "magnolia":  "03_magnolia_SOV.xlsx",
    "summit":    "04_summit_SOV.pdf",
    "heartland": "05_heartland_SOV.pdf",
    "coastal":   "06_coastal_SOV.xlsx",
}


def main() -> None:
    print("Generating broker submission emails...")
    for i, acc in enumerate(ACCOUNTS, start=1):
        attach = ATTACH_DIR / ATTACHMENT_MAP[acc.key]
        logo = LOGO_DIR / f"{i:02d}_{acc.key}_logo.png"
        if not attach.exists():
            print(f"  SKIP {acc.key}: attachment not found at {attach}")
            continue
        if not logo.exists():
            print(f"  SKIP {acc.key}: logo not found at {logo}")
            continue
        out = build_email(i, acc, attach, logo)
        print(f"  wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
