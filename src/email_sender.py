import base64
import logging
import os
import pickle
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import GMAIL_EMAIL

logger = logging.getLogger(__name__)

# If modifying these scopes, delete token.pickle.
_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
_TOKEN_PATH = "token.pickle"
_CREDENTIALS_PATH = "credentials.json"  # OAuth client secret downloaded from GCP


def setup_gmail_credentials():
    """Authenticate with Gmail API via OAuth2.

    On first run the user is taken through a browser-based consent flow.
    Subsequent runs use the cached token in *token.pickle*.

    Returns:
        A Gmail API service object, or None on failure.
    """
    creds = None

    # Load cached token
    if os.path.exists(_TOKEN_PATH):
        try:
            with open(_TOKEN_PATH, "rb") as f:
                creds = pickle.load(f)
        except Exception as exc:
            logger.warning("Could not load cached token: %s", exc)

    # Refresh or create new credentials
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:
            logger.error("Token refresh failed: %s", exc)
            creds = None

    if not creds or not creds.valid:
        if not os.path.exists(_CREDENTIALS_PATH):
            logger.error(
                "Missing %s — download OAuth client credentials from "
                "Google Cloud Console and place the file in the project root.",
                _CREDENTIALS_PATH,
            )
            return None
        try:
            flow = InstalledAppFlow.from_client_secrets_file(_CREDENTIALS_PATH, _SCOPES)
            creds = flow.run_local_server(port=0)
        except Exception as exc:
            logger.error("OAuth flow failed: %s", exc)
            return None

    # Cache for next run
    try:
        with open(_TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    except Exception as exc:
        logger.warning("Could not cache token: %s", exc)

    try:
        service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail API service created successfully")
        return service
    except Exception as exc:
        logger.error("Failed to build Gmail service: %s", exc)
        return None


def _markdown_to_html(md_text: str) -> str:
    """Convert a Markdown string to an HTML email body."""
    body_html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    return (
        "<html><head>"
        "<style>"
        "body{font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:800px;margin:auto}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ddd;padding:8px;text-align:left}"
        "th{background:#f4f4f4}"
        "h1{color:#1a1a2e}h2{color:#16213e;border-bottom:1px solid #eee;padding-bottom:4px}"
        "a{color:#0066cc}"
        "</style>"
        "</head><body>" + body_html + "</body></html>"
    )


def send_report_email(
    recipient_email: str,
    report_markdown: str,
    date: str,
    service=None,
) -> bool:
    """Send the daily report as an HTML email.

    Args:
        recipient_email: Destination address.
        report_markdown: Full Markdown report text.
        date: Report date string (YYYY-MM-DD) for the subject line.
        service: Pre-built Gmail API service (optional; created if None).

    Returns:
        True on success, False on error.
    """
    if service is None:
        service = setup_gmail_credentials()
    if service is None:
        logger.error("Cannot send email — Gmail service unavailable")
        return False

    try:
        html_body = _markdown_to_html(report_markdown)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Daily AI Market Intelligence Report - {date}"
        msg["From"] = GMAIL_EMAIL
        msg["To"] = recipient_email

        # Plain-text fallback + HTML version
        msg.attach(MIMEText(report_markdown, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        logger.info("Report email sent to %s for %s", recipient_email, date)
        return True

    except Exception as exc:
        logger.error("Failed to send email to %s: %s", recipient_email, exc)
        return False


def test_email_connection() -> bool:
    """Send a short test message to verify Gmail is working."""
    service = setup_gmail_credentials()
    if service is None:
        return False

    try:
        msg = MIMEText("Gmail connection working! AI Market Intelligence is ready.")
        msg["Subject"] = "AI Market Intelligence — Connection Test"
        msg["From"] = GMAIL_EMAIL
        msg["To"] = GMAIL_EMAIL

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        logger.info("Test email sent successfully to %s", GMAIL_EMAIL)
        return True

    except Exception as exc:
        logger.error("Test email failed: %s", exc)
        return False
