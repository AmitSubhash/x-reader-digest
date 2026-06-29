"""Read live X (x.com) session cookies from the local Brave browser.

Brave stores cookies encrypted with a key in the macOS Keychain ("Brave Safe
Storage"). browser_cookie3 handles the Keychain lookup and AES decryption, so
the pipeline can refresh its X session from Brave on every run instead of
relying on a static cookie that eventually expires.

The first access pops a macOS Keychain dialog ("python wants to use your
confidential information stored in Brave Safe Storage"). Click Always Allow so
the scheduled job can run unattended.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote


@dataclass
class XSession:
    """A logged-in X session pulled from the browser."""

    auth_token: str
    ct0: str
    user_id: str
    cookie_header: str


def _user_id_from_twid(twid: str) -> str:
    """Parse the numeric user id out of the twid cookie (u=<id>)."""
    value = unquote(twid or "")
    if value.startswith("u="):
        return value[2:].strip('"')
    return value.strip('"')


def get_x_session() -> XSession:
    """Return the current X session cookies from Brave's Default profile.

    Returns
    -------
    XSession
        auth_token, ct0, the resolved numeric user id, and a cookie header
        string suitable for twscrape.

    Raises
    ------
    RuntimeError
        If Brave has no usable X session (not logged in, or cookies missing).
    """
    import browser_cookie3

    jar = browser_cookie3.brave(domain_name="x.com")
    cookies = {c.name: c.value for c in jar}

    auth_token = cookies.get("auth_token", "")
    ct0 = cookies.get("ct0", "")
    if not auth_token or not ct0:
        raise RuntimeError(
            "Brave has no x.com auth_token/ct0; make sure you are logged into X in Brave."
        )

    user_id = _user_id_from_twid(cookies.get("twid") or "")
    # twscrape wants the same cookies the browser sends.
    wanted = ("auth_token", "ct0", "twid", "kdt", "guest_id", "att")
    header = "; ".join(f"{k}={cookies[k]}" for k in wanted if cookies.get(k))
    return XSession(auth_token=auth_token, ct0=ct0, user_id=user_id, cookie_header=header)


if __name__ == "__main__":
    session = get_x_session()
    # Never print secret values; only confirm shape.
    print(f"auth_token: {len(session.auth_token)} chars")
    print(f"ct0:        {len(session.ct0)} chars")
    print(f"user_id:    {session.user_id or '(unknown)'}")
    print(f"cookies in header: {session.cookie_header.count('=')}")
