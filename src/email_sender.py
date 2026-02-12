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

from config import EMAIL_RECIPIENTS, GMAIL_EMAIL

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


# ---------------------------------------------------------------------------
# Responsive HTML email template
# ---------------------------------------------------------------------------

_EMAIL_CSS = """\
/* Reset */
body, table, td, p, a, li, blockquote {
    -webkit-text-size-adjust: 100%;
    -ms-text-size-adjust: 100%;
    margin: 0;
    padding: 0;
}
img { border: 0; outline: none; text-decoration: none; }
table { border-collapse: collapse; mso-table-lspace: 0; mso-table-rspace: 0; }

/* Base */
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    color: #1a1a2e;
    background-color: #f0f2f5;
}

/* Container */
.wrapper { width: 100%; background-color: #f0f2f5; padding: 20px 0; }
.container {
    max-width: 680px;
    margin: 0 auto;
    background: #ffffff;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

/* Header */
.header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: #ffffff;
    padding: 28px 32px;
    text-align: center;
}
.header h1 {
    font-size: 22px;
    font-weight: 700;
    margin: 0 0 4px 0;
    letter-spacing: -0.3px;
}
.header .subtitle {
    font-size: 13px;
    color: #a8b2d1;
    margin: 0;
}

/* Content */
.content { padding: 28px 32px; }

/* Typography */
h1 { font-size: 20px; color: #1a1a2e; margin: 24px 0 12px 0; }
h2 {
    font-size: 17px;
    color: #16213e;
    border-bottom: 2px solid #e8ecf1;
    padding-bottom: 6px;
    margin: 24px 0 12px 0;
}
h3 { font-size: 15px; color: #2d3748; margin: 16px 0 8px 0; }
p { margin: 0 0 12px 0; color: #333; }

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 14px;
}
th {
    background: #f7f8fa;
    color: #1a1a2e;
    font-weight: 600;
    padding: 10px 12px;
    text-align: left;
    border-bottom: 2px solid #dee2e6;
}
td {
    padding: 8px 12px;
    border-bottom: 1px solid #edf0f4;
    color: #444;
}
tr:hover td { background: #fafbfc; }

/* Links */
a { color: #0066cc; text-decoration: none; }
a:hover { text-decoration: underline; }

/* Lists */
ul, ol { margin: 8px 0 12px 20px; padding: 0; }
li { margin-bottom: 4px; }

/* Code */
code {
    background: #f5f7fa;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 13px;
    font-family: 'SFMono-Regular', Consolas, monospace;
}
pre {
    background: #f5f7fa;
    padding: 12px 16px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 12px 0;
}
pre code { padding: 0; background: none; }

/* Blockquotes / callouts */
blockquote {
    border-left: 4px solid #0066cc;
    background: #f0f7ff;
    padding: 12px 16px;
    margin: 12px 0;
    color: #16213e;
}

/* Footer */
.footer {
    background: #f7f8fa;
    padding: 16px 32px;
    text-align: center;
    font-size: 12px;
    color: #8892a4;
    border-top: 1px solid #edf0f4;
}

/* Responsive */
@media only screen and (max-width: 600px) {
    .container { width: 100% !important; border-radius: 0 !important; }
    .header { padding: 20px 16px !important; }
    .header h1 { font-size: 18px !important; }
    .content { padding: 16px !important; }
    .footer { padding: 12px 16px !important; }
    table { font-size: 12px !important; }
    th, td { padding: 6px 8px !important; }
    h2 { font-size: 15px !important; }
}
"""


def _markdown_to_html(md_text: str, date: str = "") -> str:
    """Convert a Markdown string to a responsive HTML email body."""
    body_html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"],
    )

    subtitle = f"Report for {date}" if date else "Daily Report"

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en" xmlns="http://www.w3.org/1999/xhtml">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<meta http-equiv="X-UA-Compatible" content="IE=edge">\n'
        f"<title>AI Market Intelligence — {subtitle}</title>\n"
        f"<style>{_EMAIL_CSS}</style>\n"
        "</head>\n"
        '<body>\n'
        '<div class="wrapper">\n'
        '<div class="container">\n'
        '  <div class="header">\n'
        "    <h1>AI Market Intelligence</h1>\n"
        f'    <p class="subtitle">{subtitle}</p>\n'
        "  </div>\n"
        f'  <div class="content">\n{body_html}\n  </div>\n'
        '  <div class="footer">\n'
        "    Generated by AI Market Intelligence &middot; "
        "You are receiving this because your address is in EMAIL_RECIPIENTS\n"
        "  </div>\n"
        "</div>\n"
        "</div>\n"
        "</body>\n"
        "</html>"
    )


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send_report_email(
    recipients: str | list[str],
    report_markdown: str,
    date: str,
    service=None,
) -> bool:
    """Send the daily report as an HTML email to one or more recipients.

    Args:
        recipients: A single email address (str) or a list of addresses.
        report_markdown: Full Markdown report text.
        date: Report date string (YYYY-MM-DD) for the subject line.
        service: Pre-built Gmail API service (optional; created if None).

    Returns:
        True if the email was sent successfully to *all* recipients,
        False if any delivery failed.
    """
    if service is None:
        service = setup_gmail_credentials()
    if service is None:
        logger.error("Cannot send email — Gmail service unavailable")
        return False

    # Normalise to a list
    if isinstance(recipients, str):
        recipients = [recipients]

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for addr in recipients:
        lower = addr.strip().lower()
        if lower and lower not in seen:
            seen.add(lower)
            unique.append(addr.strip())

    if not unique:
        logger.warning("No recipients provided — skipping email")
        return False

    html_body = _markdown_to_html(report_markdown, date)
    all_ok = True

    for recipient in unique:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Daily AI Market Intelligence Report - {date}"
            msg["From"] = GMAIL_EMAIL
            msg["To"] = recipient

            # Plain-text fallback + HTML version
            msg.attach(MIMEText(report_markdown, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()

            logger.info("Report email sent to %s for %s", recipient, date)

        except Exception as exc:
            logger.error("Failed to send email to %s: %s", recipient, exc)
            all_ok = False

    return all_ok


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
