"""Classify which archived reposts are advice, and email just those.

One-time helper: asks the model to pick the advice items (research advice,
research-craft, taste, career and PhD advice, life and work wisdom) from the
archive, then sends them as a focused reading email.

Usage:
    python scripts/advice_email.py [--dry-run]
"""

from __future__ import annotations

import sys

from xdigest import store
from xdigest.gmailsend import send
from xdigest.render import render_html, render_text
from xdigest.summarize import _parse_json, claude_p


def classify_advice(items: list[dict], batch_size: int = 40) -> set[str]:
    """Return the ids of items that are advice worth reading (batched)."""
    advice_ids: set[str] = set()
    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        lines = []
        for item in batch:
            enrich = item.get("enrichment") or {}
            label = enrich.get("headline") or item.get("title") or item.get("repost_text", "")
            gist = enrich.get("gist") or enrich.get("context", "") or item.get("repost_text", "")
            lines.append(f'{item.get("id")}\t{item.get("type")}\t{label[:90]}\t{gist[:120]}')
        prompt = (
            'From this list of reposts (id, type, title, gist), return ONLY a JSON object '
            '{"ids": [...]} listing the ids (as strings) that are ADVICE Amit should read: research '
            "advice, how-to-do-research, research taste, career or job advice, PhD or mentorship advice, "
            "productivity, or genuine life and work wisdom. Be generous but precise; exclude pure news, "
            "tools, and product launches.\n\n" + "\n".join(lines)
        )
        try:
            result = _parse_json(claude_p(prompt, timeout=150))
            advice_ids |= {str(x) for x in result.get("ids", [])}
            print(f"  batch {start // batch_size + 1}: +{len(result.get('ids', []))}")
        except Exception as exc:  # noqa: BLE001 - keep going if one batch fails
            print(f"  batch {start // batch_size + 1} failed: {str(exc)[:80]}")
    return advice_ids


def main(dry_run: bool) -> None:
    items = store.load_all_items()
    advice_ids = classify_advice(items)
    advice = [i for i in items if str(i.get("id")) in advice_ids]
    print(f"{len(advice)} advice items of {len(items)}")
    if not advice:
        return
    subj = f"Advice to read: {len(advice)} pieces from your reposts"
    if dry_run:
        import pathlib
        pathlib.Path("out").mkdir(exist_ok=True)
        pathlib.Path("out/advice_preview.html").write_text(render_html(advice), encoding="utf-8")
        print("[dry-run] wrote out/advice_preview.html")
        return
    mid = send("atsubhas@iu.edu", subj, render_html(advice), render_text(advice))
    print(f"SENT id={mid}: {subj}")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
