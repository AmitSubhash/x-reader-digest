"""Send the digest via the Gmail API, reusing the paper2kindle send token.

The paper2kindle OAuth token carries the gmail.send scope, which is exactly
what is needed to send (not draft) email. This is the reliable delivery path:
it is an API call, not GUI scripting of Mail.app, so it does not depend on
Automation permissions or Mail being focused. Same mechanism that sends your
documents to Kindle.
"""

from __future__ import annotations

import base64
import json
import pathlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
PAPER2KINDLE = pathlib.Path.home() / ".paper2kindle"
TOKEN_PATH = PAPER2KINDLE / "token.json"
CONFIG_PATH = PAPER2KINDLE / "config.json"


def _sender() -> str:
    """Resolve the From address from paper2kindle config (send scope cannot
    read the profile)."""
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text()).get("sender_email", "me")
    return "me"


def _credentials() -> Credentials:
    """Load and refresh the paper2kindle send-scoped credentials."""
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(f"no paper2kindle token at {TOKEN_PATH}")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def send(to_address: str, subject: str, html_body: str, text_body: str) -> str:
    """Send an HTML+text email and return the Gmail message id (proof of send).

    Parameters
    ----------
    to_address : str
        Recipient.
    subject : str
        Subject line.
    html_body : str
        HTML version of the message.
    text_body : str
        Plain-text fallback.

    Returns
    -------
    str
        The sent message id from the Gmail API.
    """
    service = build("gmail", "v1", credentials=_credentials())

    message = MIMEMultipart("alternative")
    message["To"] = to_address
    message["From"] = _sender()
    message["Subject"] = subject
    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent.get("id", "")
