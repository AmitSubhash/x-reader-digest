"""Create a Gmail draft of the digest, reusing the paper2kindle OAuth client.

The paper2kindle token only carries the gmail.send scope, which cannot create
drafts, so this module keeps its own token with the gmail.compose scope. Run
`python -m xdigest.draft auth` once to grant it (opens a browser).
"""

from __future__ import annotations

import base64
import pathlib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
CREDENTIALS_PATH = pathlib.Path.home() / ".paper2kindle" / "credentials.json"
TOKEN_PATH = pathlib.Path.home() / ".config" / "xdigest" / "gmail_compose_token.json"


def authorize() -> None:
    """Run the one-time OAuth consent flow to obtain a compose-scoped token."""
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(f"missing OAuth client at {CREDENTIALS_PATH}")
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    print(f"authorized; token written to {TOKEN_PATH}")


def _load_credentials() -> Credentials:
    """Load and refresh the compose-scoped credentials."""
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"no compose token at {TOKEN_PATH}; run: python -m xdigest.draft auth"
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def create_draft(to_address: str, subject: str, html_body: str, text_body: str) -> str:
    """Create a Gmail draft and return its draft id.

    Parameters
    ----------
    to_address : str
        Recipient (usually yourself).
    subject : str
        Email subject line.
    html_body : str
        HTML version of the digest.
    text_body : str
        Plain-text fallback.

    Returns
    -------
    str
        The created Gmail draft id.
    """
    service = build("gmail", "v1", credentials=_load_credentials())
    profile = service.users().getProfile(userId="me").execute()
    sender = profile.get("emailAddress", "me")

    message = MIMEMultipart("alternative")
    message["To"] = to_address
    message["From"] = sender
    message["Subject"] = subject
    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw}})
        .execute()
    )
    return draft["id"]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        authorize()
    else:
        print("usage: python -m xdigest.draft auth")
