"""Build reliable "read more" links from the analyzer's references.

The model names entities (people, papers, concepts); we turn those into search
URLs deterministically rather than trusting model-generated URLs, so every link
works. People and papers go to Google Scholar, everything else to Google.
"""

from __future__ import annotations

from urllib.parse import quote_plus


def _search_url(name: str, kind: str) -> str:
    query = quote_plus(name)
    if kind in ("person", "paper"):
        return f"https://scholar.google.com/scholar?q={query}"
    return f"https://www.google.com/search?q={query}"


def reference_links(references: list[dict] | None) -> list[tuple[str, str]]:
    """Return (label, url) pairs for each named reference."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for ref in references or []:
        name = str((ref or {}).get("name", "")).strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append((name, _search_url(name, str((ref or {}).get("kind", "")))))
    return out


def read_more_url(query: str) -> str:
    """Return a Google search URL for a dig-deeper query, or '' if empty."""
    query = (query or "").strip()
    return f"https://www.google.com/search?q={quote_plus(query)}" if query else ""
