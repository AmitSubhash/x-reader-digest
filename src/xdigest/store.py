"""Persist processed digest items to the private data repo as JSONL.

The archive is the durable record of everything captured (one JSON object per
line, deduplicated by resolved URL). The website is regenerated from it, and the
daily job commits and pushes it to your private GitHub repo.
"""

from __future__ import annotations

import json
import pathlib

CONFIG_PATH = pathlib.Path.home() / ".config" / "xdigest" / "config.json"
DEFAULT_DATA_REPO = pathlib.Path.home() / "Projects" / "x-reader-digest-data"

# Verdicts that count as "worth your time" on either axis.
POSITIVE = {"READ", "WATCH"}


def _config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def data_repo() -> pathlib.Path:
    """Return the path to the private data repo (configurable)."""
    return pathlib.Path(_config().get("data_repo", str(DEFAULT_DATA_REPO)))


def items_path() -> pathlib.Path:
    """Return the JSONL archive path inside the data repo."""
    return data_repo() / "data" / "items.jsonl"


def is_recommended(item: dict) -> bool:
    """True when either verdict marks the item worth the user's time."""
    enrich = item.get("enrichment") or {}
    return (
        str(enrich.get("research_verdict", "")).upper() in POSITIVE
        or str(enrich.get("general_verdict", "")).upper() in POSITIVE
    )


def load_seen_urls() -> set[str]:
    """Return the set of resolved URLs already archived."""
    path = items_path()
    if not path.exists():
        return set()
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            seen.add(json.loads(line).get("final_url", ""))
        except json.JSONDecodeError:
            continue
    return seen


def append_items(items: list[dict]) -> int:
    """Append new items to the archive, skipping URLs already present.

    Returns
    -------
    int
        Number of items actually written.
    """
    path = items_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = load_seen_urls()
    written = 0
    with path.open("a", encoding="utf-8") as handle:
        for item in items:
            url = item.get("final_url", "")
            if not url or url in seen:
                continue
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            seen.add(url)
            written += 1
    return written


def load_all_items() -> list[dict]:
    """Load every archived item, newest first by capture date."""
    path = items_path()
    if not path.exists():
        return []
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    items.sort(key=lambda d: d.get("date", ""), reverse=True)
    return items
