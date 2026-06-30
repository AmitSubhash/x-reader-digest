"""Capture recent reposts from your own X timeline with twscrape.

X reposts (retweets and quote tweets) are public and appear on your profile
timeline, so no paid API is needed. This module refreshes its X session from
the local Brave browser on every run (see brave_cookies), registers it with
twscrape, reads your timeline, and returns the new reposts that contain
external links, tracking a high-water mark so each run only returns reposts it
has not seen before.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from twscrape import API

from .brave_cookies import get_x_session

CONFIG_DIR = pathlib.Path.home() / ".config" / "xdigest"
ACCOUNTS_DB = CONFIG_DIR / "accounts.db"
USERID_PATH = CONFIG_DIR / "user_id.txt"
STATE_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "state" / "last_tweet_id.txt"
ACCOUNT_USERNAME = "brave_session"

_SKIP_HOSTS = {"twitter.com", "x.com", "www.twitter.com", "www.x.com", "t.co", "pic.twitter.com"}


@dataclass
class Repost:
    """A single repost (retweet or quote) carrying external links."""

    tweet_id: int
    date: str
    kind: str  # "retweet" or "quote"
    text: str
    urls: list[str] = field(default_factory=list)


def _external_urls(tweet) -> list[str]:
    """Pull expanded, non-twitter, non-media URLs from a tweet's links."""
    urls: list[str] = []
    for link in getattr(tweet, "links", None) or []:
        url = getattr(link, "url", None) or getattr(link, "expanded_url", None)
        if not url:
            continue
        host = (urlparse(url).hostname or "").lower()
        if host in _SKIP_HOSTS or host.endswith(".twimg.com"):
            continue
        if url not in urls:
            urls.append(url)
    return urls


def _read_last_id() -> int:
    if STATE_PATH.exists():
        try:
            return int(STATE_PATH.read_text().strip() or "0")
        except ValueError:
            return 0
    return 0


def _write_last_id(tweet_id: int) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(str(tweet_id), encoding="utf-8")


def set_last_id(tweet_id: int) -> None:
    """Set the seen high-water mark (used after a backfill)."""
    if tweet_id and tweet_id > _read_last_id():
        _write_last_id(tweet_id)


async def _refresh_from_brave() -> str:
    """Pull fresh cookies from Brave and (re)register the twscrape account.

    Returns
    -------
    str
        The numeric user id of the logged-in account.
    """
    session = get_x_session()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if session.user_id:
        USERID_PATH.write_text(session.user_id, encoding="utf-8")

    api = API(str(ACCOUNTS_DB))
    try:
        await api.pool.delete_accounts(ACCOUNT_USERNAME)
    except Exception:  # noqa: BLE001 - first run has nothing to delete
        pass
    await api.pool.add_account(
        username=ACCOUNT_USERNAME,
        password="brave-cookie-auth",
        email=f"{ACCOUNT_USERNAME}@cookie.local",
        email_password="brave-cookie-auth",
        cookies=session.cookie_header,
    )
    await api.pool.login_all()
    return session.user_id


def _user_id() -> str:
    if USERID_PATH.exists():
        return USERID_PATH.read_text().strip()
    return ""


async def _fetch(
    limit: int,
    update_state: bool,
    refresh: bool,
    since_date: Optional[dt.date] = None,
    use_state: bool = True,
) -> list[Repost]:
    """Fetch reposts (retweets only) with external links from your timeline.

    Daily mode (use_state=True) returns retweets newer than the high-water mark.
    Backfill mode (since_date set, use_state=False) returns every retweet on or
    after the cutoff date. Quote-tweets are excluded.
    """
    user_id = await _refresh_from_brave() if refresh else _user_id()
    if not user_id:
        raise RuntimeError("no user id; run a refresh from Brave first")

    api = API(str(ACCOUNTS_DB))
    last_id = _read_last_id() if use_state else 0
    reposts: list[Repost] = []
    max_seen = last_id

    consecutive_old = 0
    async for tweet in api.user_tweets(int(user_id), limit=limit):
        tweet_date = getattr(tweet, "date", None)
        if since_date is not None and tweet_date is not None and tweet_date.date() < since_date:
            # The timeline is mostly newest first, but a pinned tweet (or minor
            # reordering) can place an old tweet near the top, so skip stray old
            # tweets and only stop once we are clearly past the cutoff.
            consecutive_old += 1
            if consecutive_old >= 12:
                break
            continue
        consecutive_old = 0
        if use_state and tweet.id <= last_id:
            continue
        max_seen = max(max_seen, tweet.id)
        source = getattr(tweet, "retweetedTweet", None)  # retweets only, no quotes
        if source is None:
            continue
        urls = _external_urls(source) or _external_urls(tweet)
        if not urls:
            continue
        reposts.append(
            Repost(
                tweet_id=tweet.id,
                date=tweet_date.isoformat() if tweet_date else "",
                kind="retweet",
                text=(getattr(source, "rawContent", "") or "")[:500],
                urls=urls,
            )
        )

    if update_state and use_state and max_seen > last_id:
        _write_last_id(max_seen)
    return reposts


def fetch_new_reposts(limit: int = 60, update_state: bool = True, refresh: bool = True) -> list[Repost]:
    """Synchronous wrapper: new retweets with external links since last run."""
    return asyncio.run(_fetch(limit=limit, update_state=update_state, refresh=refresh))


def fetch_backfill(since: str, limit: int = 2000, refresh: bool = True) -> list[Repost]:
    """Return every retweet with external links on or after a cutoff date.

    Parameters
    ----------
    since : str
        ISO date string, for example "2026-05-01".
    limit : int
        Maximum timeline tweets to scan (paged by twscrape).
    refresh : bool
        Pull fresh cookies from Brave first.
    """
    cutoff = dt.date.fromisoformat(since)
    return asyncio.run(
        _fetch(limit=limit, update_state=False, refresh=refresh, since_date=cutoff, use_state=False)
    )


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "fetch":
        rows = fetch_new_reposts(update_state=False)
        print(f"{len(rows)} new retweets with links")
        for rp in rows:
            print(f"[{rp.kind}] {rp.tweet_id} {rp.date}")
            for u in rp.urls:
                print("    ", u)
    elif len(sys.argv) >= 3 and sys.argv[1] == "backfill":
        rows = fetch_backfill(sys.argv[2])
        print(f"{len(rows)} retweets with links since {sys.argv[2]}")
        for rp in rows:
            print(f"[{rp.kind}] {rp.tweet_id} {rp.date} ({len(rp.urls)} links)")
    elif len(sys.argv) >= 2 and sys.argv[1] == "refresh":
        uid = asyncio.run(_refresh_from_brave())
        print(f"refreshed from Brave; user_id={uid}")
    else:
        print("usage:\n  python -m xdigest.capture refresh\n"
              "  python -m xdigest.capture fetch\n"
              "  python -m xdigest.capture backfill 2026-05-01")
