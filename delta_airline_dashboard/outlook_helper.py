import os
import sys
import tempfile
import urllib.parse
import webbrowser
from datetime import datetime


def open_outlook_with_report(
    pdf_bytes: bytes,
    recipient: str = "",
    company_name: str = "Delta Air Lines (DAL)",
    summary_highlights: str = "",
) -> tuple[bool, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"DAL_Executive_Briefing_{timestamp}.pdf"
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    subject = f"Client Meeting Prep: {company_name} – Financial, Risk & Hedging Briefing"
    body = (
        f"Hi Team,\n\n"
        f"Ahead of our upcoming client meeting with {company_name}, please find attached the "
        f"latest financial analysis, DCF valuation summary, and corporate hedging strategy briefing.\n\n"
        f"Key Highlights:\n"
        f"{summary_highlights}\n\n"
        f"Please review the attached PDF prior to our call.\n\n"
        f"Best regards,\n"
        f"Corporate & Transaction Banking Sales"
    )

    if sys.platform == "win32":
        try:
            import pythoncom
            import win32com.client as win32

            pythoncom.CoInitialize()
            outlook = win32.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.To = recipient
            mail.Subject = subject
            mail.Body = body
            mail.Attachments.Add(os.path.abspath(file_path))
            mail.Display(False)
            return True, f"Outlook draft opened with '{filename}' attached."
        except Exception as e:
            mailto_url = (
                f"mailto:{urllib.parse.quote(recipient)}"
                f"?subject={urllib.parse.quote(subject)}"
                f"&body={urllib.parse.quote(body)}"
            )
            webbrowser.open(mailto_url)
            return False, f"Outlook COM unavailable ({e}). Opened default email client via mailto. Saved report at: {file_path}"

    mailto_url = (
        f"mailto:{urllib.parse.quote(recipient)}"
        f"?subject={urllib.parse.quote(subject)}"
        f"&body={urllib.parse.quote(body)}"
    )
    webbrowser.open(mailto_url)
    return False, f"Opened default email client. Saved report at: {file_path}"