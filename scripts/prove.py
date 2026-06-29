"""Prove the extract + summarize engine on URLs passed as arguments.

Usage:
    python scripts/prove.py <url> [<url> ...]
"""

from __future__ import annotations

import json
import sys

from xdigest.extract import extract
from xdigest.summarize import summarize_item


def main(urls: list[str]) -> None:
    for url in urls:
        print("=" * 78)
        print("INPUT:", url)
        item = extract(url)
        print(f"  kind={item.kind}  final={item.final_url}")
        print(f"  title={item.title!r}")
        print(f"  reading_minutes={item.reading_minutes}  text_chars={len(item.text)}")
        if item.error:
            print("  EXTRACT ERROR:", item.error)
        enriched = summarize_item(item)
        print("  --- enrichment ---")
        if enriched["enrich_error"]:
            print("  ENRICH ERROR:", enriched["enrich_error"])
        else:
            print(json.dumps(enriched["enrichment"], indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
