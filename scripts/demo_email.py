"""Build a sample digest email from URLs and write the HTML to out/.

Usage:
    python scripts/demo_email.py <url> [<url> ...]
"""

from __future__ import annotations

import pathlib
import sys

from xdigest.extract import extract
from xdigest.render import render_html, subject
from xdigest.summarize import summarize_item


def main(urls: list[str]) -> None:
    enriched = []
    for url in urls:
        print("processing:", url)
        enriched.append(summarize_item(extract(url)))
    out_dir = pathlib.Path(__file__).resolve().parent.parent / "out"
    out_dir.mkdir(exist_ok=True)
    html_path = out_dir / "sample_digest.html"
    html_path.write_text(render_html(enriched), encoding="utf-8")
    print("subject:", subject(enriched))
    print("wrote:", html_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
