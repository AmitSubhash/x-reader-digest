"""Resolve repost links and extract readable content.

For each URL found in a repost this module decides what kind of link it is
(article, YouTube video, bare tweet, or other) and pulls the content needed
downstream: the full article text for articles, or the transcript plus
metadata for videos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional
from urllib.parse import parse_qs, urlparse

import requests

ItemKind = Literal["article", "youtube", "tweet", "other"]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
_TWEET_HOSTS = {"twitter.com", "www.twitter.com", "x.com", "www.x.com", "mobile.twitter.com"}
# Hosts that are not readable articles; shown as a bare link, not summarized.
_OTHER_HOSTS = {
    "open.spotify.com", "spotify.com", "podcasts.apple.com", "music.apple.com",
    "soundcloud.com", "tiktok.com", "www.tiktok.com", "instagram.com", "www.instagram.com",
}
_WORDS_PER_MINUTE = 220
# Above this, a PDF is treated as a long document: inline the first part only.
_PDF_INLINE_CHAR_CAP = 45000


@dataclass
class ExtractedItem:
    """One repost link after resolution and content extraction.

    Parameters
    ----------
    source_url : str
        The URL as it appeared in the repost (often a t.co short link).
    final_url : str
        The resolved destination after following redirects.
    kind : ItemKind
        Classification of the link.
    title : str
        Best-effort title of the content.
    text : str
        Full readable article text (markdown) for articles, or the transcript
        for videos. Empty when extraction failed.
    meta : dict
        Type-specific metadata (author, date, channel, duration, etc.).
    reading_minutes : int
        Estimated reading time for articles, runtime in minutes for videos.
    error : str, optional
        Populated when extraction failed, so the digest can still show the link.
    """

    source_url: str
    final_url: str
    kind: ItemKind
    title: str = ""
    text: str = ""
    meta: dict = field(default_factory=dict)
    reading_minutes: int = 0
    error: Optional[str] = None


def resolve_url(url: str, timeout: float = 12.0) -> str:
    """Follow redirects (for example t.co) to the final destination URL.

    Parameters
    ----------
    url : str
        Possibly shortened URL.
    timeout : float
        Per-request timeout in seconds.

    Returns
    -------
    str
        The final URL, or the input URL if resolution failed.
    """
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout, headers=_HEADERS)
        if resp.url:
            return resp.url
    except requests.RequestException:
        pass
    try:
        resp = requests.get(url, allow_redirects=True, timeout=timeout, headers=_HEADERS, stream=True)
        return resp.url or url
    except requests.RequestException:
        return url


def classify(url: str) -> ItemKind:
    """Classify a resolved URL into a content kind.

    Parameters
    ----------
    url : str
        A resolved (non-shortened) URL.

    Returns
    -------
    ItemKind
        One of "youtube", "tweet", "article", or "other".
    """
    host = (urlparse(url).hostname or "").lower()
    if host in _YOUTUBE_HOSTS:
        return "youtube"
    if host in _TWEET_HOSTS:
        return "tweet"
    if host in _OTHER_HOSTS:
        return "other"
    if host:
        return "article"
    return "other"


def youtube_id(url: str) -> Optional[str]:
    """Extract the 11-character YouTube video id from a URL, if present."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.lstrip("/").split("/")[0]
        return candidate or None
    if "youtube" in host:
        if parsed.path.startswith(("/shorts/", "/embed/", "/v/")):
            return parsed.path.split("/")[2]
        values = parse_qs(parsed.query).get("v")
        if values:
            return values[0]
    match = re.search(r"([0-9A-Za-z_-]{11})", parsed.path)
    return match.group(1) if match else None


def extract_article(source_url: str, final_url: str) -> ExtractedItem:
    """Extract the main readable text and metadata from an article URL.

    Uses trafilatura for boilerplate-free extraction and markdown output.
    """
    import trafilatura

    item = ExtractedItem(source_url=source_url, final_url=final_url, kind="article")
    downloaded = trafilatura.fetch_url(final_url)
    if not downloaded:
        item.error = "could not download page"
        return item

    text = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_links=True,
        include_images=False,
        favor_precision=True,
    )
    metadata = trafilatura.extract_metadata(downloaded)

    if metadata is not None:
        item.title = metadata.title or ""
        item.meta = {
            "author": metadata.author or "",
            "date": metadata.date or "",
            "sitename": metadata.sitename or (urlparse(final_url).hostname or ""),
            "description": metadata.description or "",
        }
    if not text:
        item.error = "no readable content extracted"
        return item

    item.text = text.strip()
    word_count = len(item.text.split())
    item.meta["word_count"] = word_count
    item.reading_minutes = max(1, round(word_count / _WORDS_PER_MINUTE))
    if not item.title:
        item.title = (urlparse(final_url).hostname or "Article")
    return item


def _fetch_transcript(video_id: str) -> str:
    """Fetch a YouTube transcript across youtube-transcript-api versions."""
    from youtube_transcript_api import YouTubeTranscriptApi

    def _snippet_text(snippet: object) -> str:
        if isinstance(snippet, dict):
            return snippet.get("text", "")
        return getattr(snippet, "text", "")

    # 1.x instance API
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        snippets = getattr(fetched, "snippets", fetched)
        return " ".join(_snippet_text(s) for s in snippets).strip()
    except Exception:  # noqa: BLE001 - fall through to legacy API
        pass
    # legacy 0.x classmethod API
    try:
        rows = YouTubeTranscriptApi.get_transcript(video_id)  # type: ignore[attr-defined]
        return " ".join(row["text"] for row in rows).strip()
    except Exception:  # noqa: BLE001
        return ""


def extract_youtube(source_url: str, final_url: str) -> ExtractedItem:
    """Extract metadata and transcript for a YouTube video.

    Uses yt-dlp for metadata (no download) and youtube-transcript-api for the
    transcript, falling back to the yt-dlp description when no transcript exists.
    """
    import yt_dlp

    item = ExtractedItem(source_url=source_url, final_url=final_url, kind="youtube")
    vid = youtube_id(final_url)
    if not vid or "list=" in final_url and "watch" not in final_url:
        item.title = "YouTube playlist or channel"
        item.error = "not a single video (playlist or channel link)"
        return item

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(final_url, download=False)
    except Exception as exc:  # noqa: BLE001
        item.error = f"yt-dlp metadata failed: {exc}"
        info = {}

    duration_s = int(info.get("duration") or 0)
    item.title = info.get("title") or "YouTube video"
    item.reading_minutes = max(1, round(duration_s / 60)) if duration_s else 0
    item.meta = {
        "channel": info.get("channel") or info.get("uploader") or "",
        "duration_seconds": duration_s,
        "duration_human": _hms(duration_s),
        "view_count": info.get("view_count"),
        "upload_date": info.get("upload_date") or "",
        "description": (info.get("description") or "")[:2000],
        "video_id": vid or info.get("id") or "",
    }

    transcript = _fetch_transcript(vid) if vid else ""
    if transcript:
        item.text = transcript
        item.meta["has_transcript"] = True
    else:
        item.text = item.meta["description"]
        item.meta["has_transcript"] = False
        if not item.text:
            item.error = "no transcript or description available"
    return item


def _looks_like_pdf(url: str) -> bool:
    """True when the URL path points at a PDF file."""
    return (urlparse(url).path or "").lower().endswith(".pdf")


def extract_pdf(source_url: str, final_url: str) -> ExtractedItem:
    """Download and extract text from a PDF (paper, lecture notes, book).

    Long PDFs are treated as documents: only the first part is inlined and the
    item is flagged truncated so the digest links to the full file.
    """
    import io

    from pypdf import PdfReader

    item = ExtractedItem(source_url=source_url, final_url=final_url, kind="article")
    try:
        resp = requests.get(final_url, timeout=30, headers=_HEADERS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        item.error = f"could not download pdf: {exc}"
        return item

    try:
        reader = PdfReader(io.BytesIO(resp.content))
        pages = len(reader.pages)
    except Exception as exc:  # noqa: BLE001 - malformed/encrypted PDFs
        item.error = f"could not parse pdf: {exc}"
        return item

    chunks: list[str] = []
    total = 0
    used_pages = 0
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - per-page extraction can fail
            page_text = ""
        used_pages += 1
        if page_text:
            chunks.append(page_text)
            total += len(page_text)
        if total >= _PDF_INLINE_CHAR_CAP:
            break

    text = "\n\n".join(chunks).strip()
    if not text:
        item.error = "no extractable text (likely a scanned or image-only PDF)"
        return item

    item.text = text[:_PDF_INLINE_CHAR_CAP]
    word_count = len(item.text.split())
    item.reading_minutes = max(1, round(word_count / _WORDS_PER_MINUTE))

    title = ""
    try:
        if reader.metadata and reader.metadata.title:
            title = str(reader.metadata.title).strip()
    except Exception:  # noqa: BLE001
        title = ""
    filename = (urlparse(final_url).path or "").rsplit("/", 1)[-1] or "document.pdf"
    item.title = title or filename
    item.meta = {
        "pdf": True,
        "pages": pages,
        "truncated": used_pages < pages,
        "sitename": urlparse(final_url).hostname or "",
        "word_count": word_count,
    }
    return item


def extract(source_url: str) -> ExtractedItem:
    """Resolve and extract a single repost URL end to end.

    Parameters
    ----------
    source_url : str
        The URL from the repost (may be a t.co short link).

    Returns
    -------
    ExtractedItem
        Populated with content for articles, PDFs, and videos, or an error.
    """
    final_url = resolve_url(source_url)
    kind = classify(final_url)
    if kind == "youtube":
        return extract_youtube(source_url, final_url)
    if kind == "article" and _looks_like_pdf(final_url):
        return extract_pdf(source_url, final_url)
    if kind == "article":
        return extract_article(source_url, final_url)
    return ExtractedItem(
        source_url=source_url,
        final_url=final_url,
        kind=kind,
        title=final_url,
        error=None if kind == "tweet" else "unsupported link type",
    )


def _hms(seconds: int) -> str:
    """Format a duration in seconds as H:MM:SS or M:SS."""
    if not seconds:
        return ""
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
