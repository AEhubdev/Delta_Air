"""Build email drafts for the Streamlit viewer's local mail application.

Streamlit Cloud runs Python on a remote server, so server-side COM and
``webbrowser.open`` cannot launch Outlook on the viewer's computer. These
helpers instead create a client-side ``mailto:`` link and a portable ``.eml``
draft that the viewer can download and open in Outlook.
"""

from email.message import EmailMessage
from urllib.parse import quote


def _email_content(
    recipient: str = "",
    company_name: str = "Selected company",
    summary_highlights: str = "",
) -> tuple[str, str, str]:
    subject = f"Client Meeting Prep: {company_name} - Financial, Risk & Hedging Briefing"
    body = (
        f"Hi Team,\n\n"
        f"Ahead of our upcoming client meeting with {company_name}, please find the "
        "latest financial analysis, DCF valuation summary, and corporate hedging "
        "strategy briefing attached.\n\n"
        f"Key Highlights:\n{summary_highlights}\n\n"
        "Please review the attached PDF prior to our call.\n\n"
        "Best regards,\n"
        "Corporate & Transaction Banking Sales"
    )
    return recipient.strip(), subject, body


def build_mailto_url(
    recipient: str = "",
    company_name: str = "Selected company",
    summary_highlights: str = "",
) -> str:
    """Return a mailto URL that the user's browser opens on their own device."""
    recipient, subject, body = _email_content(recipient, company_name, summary_highlights)
    encoded_recipient = quote(recipient, safe="@,;")
    return f"mailto:{encoded_recipient}?subject={quote(subject)}&body={quote(body)}"


def build_email_eml(
    pdf_bytes: bytes,
    recipient: str = "",
    company_name: str = "Selected company",
    summary_highlights: str = "",
    filename: str = "Executive_Briefing.pdf",
) -> bytes:
    """Build an Outlook-compatible .eml file with the generated PDF attached."""
    recipient, subject, body = _email_content(recipient, company_name, summary_highlights)
    message = EmailMessage()
    if recipient:
        message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=filename,
    )
    return message.as_bytes()
