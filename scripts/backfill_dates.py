"""One-time migration: stamp repost dates onto already-archived items.

Earlier archive runs dropped the repost date when flattening links. This
re-captures only the url -> (date, tweet_id) map (no summarizing) and patches
the archive in place, then regenerates the site.

Usage:
    python scripts/backfill_dates.py 2026-05-01
"""

from __future__ import annotations

import json
import sys

from xdigest import site, store
from xdigest.capture import fetch_backfill


def main(since: str) -> None:
    reposts = fetch_backfill(since)
    url_meta: dict[str, tuple[str, int]] = {}
    for repost in reposts:
        for url in repost.urls:
            url_meta.setdefault(url, (repost.date, repost.tweet_id))
    print(f"captured {len(url_meta)} url->date entries from {len(reposts)} reposts")

    path = store.items_path()
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    patched = 0
    for item in items:
        source = item.get("source_url", "")
        if not item.get("date") and source in url_meta:
            item["date"], item["id"] = url_meta[source]
            patched += 1
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"patched {patched} of {len(items)} items")

    count = site.generate(store.load_all_items(), store.data_repo() / "docs")
    print(f"regenerated site with {count} items")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-05-01")
