"""Create a Mail.app draft via AppleScript (osascript), reusing iu-mail-mcp.

This is the default delivery path: it saves a draft to the Mail.app account's
Drafts and never sends, which honours the draft-and-review rule and works
headless from a launchd job (the only one-time cost is granting the process
Automation access to Mail). The plain-text digest is the body; the rich HTML is
attached so it can be opened with formatting.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Optional

DEFAULT_ACCOUNT = "Exchange"  # Amit's IU mailbox as named in Mail.app

# Reads the body from a UTF-8 file so large digests never hit ARG_MAX, then
# saves an unsent draft. argv: account, to, subject, body_file, attach_file.
_SCRIPT = """
on run argv
  set acctName to item 1 of argv
  set toAddr to item 2 of argv
  set subj to item 3 of argv
  set bodyFile to item 4 of argv
  set attachFile to item 5 of argv
  set bodyText to (read (POSIX file bodyFile as alias) as «class utf8»)
  set sendMode to (item 6 of argv)
  with timeout of 90 seconds
    tell application "Mail"
      set newMsg to make new outgoing message with properties {subject:subj, content:bodyText, visible:false}
      try
        set sender of newMsg to (item 1 of (email addresses of account acctName))
      end try
      tell newMsg to make new to recipient at end of to recipients with properties {address:toAddr}
      if attachFile is not "" then
        try
          tell newMsg to make new attachment with properties {file name:(POSIX file attachFile as alias)} at after the last paragraph of content
        end try
      end if
      if sendMode is "send" then
        send newMsg
      else
        save newMsg
      end if
    end tell
  end timeout
  return "ok"
end run
"""


def create_draft(
    to_address: str,
    subject: str,
    text_body: str,
    html_path: Optional[str] = None,
    account: str = DEFAULT_ACCOUNT,
    timeout: float = 120.0,
    send: bool = False,
) -> None:
    """Save a Mail.app draft, or send it when send=True.

    Parameters
    ----------
    to_address : str
        Recipient (usually yourself).
    subject : str
        Subject line.
    text_body : str
        Plain-text digest used as the message body.
    html_path : str, optional
        Path to the rich HTML digest, attached for formatted viewing.
    account : str
        Mail.app account name to draft from.
    timeout : float
        Subprocess timeout in seconds.
    send : bool
        When True, send the message instead of saving a draft. Only use with an
        explicit per-message approval.

    Raises
    ------
    RuntimeError
        If osascript fails (for example Automation access not granted).
    """
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write(text_body)
        body_file = handle.name

    args = [account, to_address, subject, body_file, html_path or "", "send" if send else "draft"]
    try:
        proc = subprocess.run(
            ["osascript", "-", *args],
            input=_SCRIPT.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
        )
    finally:
        Path(body_file).unlink(missing_ok=True)

    if proc.returncode != 0:
        raise RuntimeError(f"osascript failed: {proc.stderr.decode('utf-8', 'replace').strip()[:400]}")


if __name__ == "__main__":
    create_draft(
        to_address="atsubhas@iu.edu",
        subject="[xdigest test] Mail.app draft path works",
        text_body="If you can read this in your Exchange Drafts, the Mail.app draft path works.\n",
    )
    print("draft saved to Exchange/Drafts (not sent)")
