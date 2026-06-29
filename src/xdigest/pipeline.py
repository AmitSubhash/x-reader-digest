"""Orchestrate the digest end to end.

    run                 capture new retweets, process, archive, rebuild site,
                        push to the private repo, create a Mail.app draft
    backfill 2026-05-01 same, but over every retweet since the cutoff date
    run --dry-run       build locally, no draft, no push, no state change

The website is regenerated from the full archive; the email draft contains only
this run's new recommended items.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess

from . import store
from .extract import extract
from .render import render_html, render_text, subject
from .site import generate as generate_site
from .summarize import summarize_item

CONFIG_PATH = pathlib.Path.home() / ".config" / "xdigest" / "config.json"
OUT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "out"
DEFAULT_TO = "atsubhas@iu.edu"
EMAIL_ITEM_CAP = 50  # cap items inlined in one email; the site holds everything


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def _exclude(item) -> bool:
    """Drop book-length PDFs (over 30 pages) and unsupported links."""
    meta = item.meta or {}
    if meta.get("pdf") and int(meta.get("pages") or 0) > 30:
        return True
    return item.kind in {"tweet", "other"}


def process_urls(urls: list[str], model: str) -> list[dict]:
    """Extract and summarize each URL, skipping excluded links."""
    enriched: list[dict] = []
    for url in urls:
        item = extract(url)
        if _exclude(item):
            print(f"  skip ({item.kind}{' pdf' if (item.meta or {}).get('pdf') else ''}): {url}")
            continue
        print("  ->", url)
        record = summarize_item(item, model=model)
        record["recommended"] = store.is_recommended(record)
        enriched.append(record)
    return enriched


def _git_push(repo: pathlib.Path, message: str) -> None:
    """Commit and push the data repo, authored as Amit (no AI attribution)."""
    if not (repo / ".git").exists():
        print(f"  [git] {repo} is not a git repo; skipping push")
        return
    env = {
        "GIT_AUTHOR_NAME": "Amit T Subhash",
        "GIT_AUTHOR_EMAIL": "amitsubhashco@gmail.com",
        "GIT_COMMITTER_NAME": "Amit T Subhash",
        "GIT_COMMITTER_EMAIL": "amitsubhashco@gmail.com",
    }
    import os

    full_env = {**os.environ, **env}
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=False, env=full_env)
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True, env=full_env
    )
    if not status.stdout.strip():
        print("  [git] nothing to commit")
        return
    subprocess.run(["git", "-C", str(repo), "commit", "-m", message], check=False, env=full_env)
    push = subprocess.run(["git", "-C", str(repo), "push"], capture_output=True, text=True, env=full_env)
    print("  [git] pushed" if push.returncode == 0 else f"  [git] push failed: {push.stderr.strip()[:200]}")


def _maybe_push_phone(config: dict, text: str) -> None:
    """Send a best-effort phone notification if enabled in config."""
    if not config.get("push_to_phone"):
        return
    try:
        subprocess.run(["push-to-phone", text], check=False, timeout=20)
    except Exception as exc:  # noqa: BLE001 - notification is non-critical
        print(f"  [push] skipped: {exc}")


def _gather_urls(args) -> tuple[list[str], int]:
    """Return (urls, newest_tweet_id) for the chosen source."""
    if args.urls:
        return list(dict.fromkeys(args.urls)), 0
    from .capture import fetch_backfill, fetch_new_reposts

    if args.since:
        reposts = fetch_backfill(args.since)
    else:
        advance = not args.dry_run and not args.no_state
        reposts = fetch_new_reposts(limit=args.limit, update_state=advance)

    urls: list[str] = []
    newest = 0
    for repost in reposts:
        newest = max(newest, repost.tweet_id)
        for url in repost.urls:
            if url not in urls:
                urls.append(url)
    return urls, newest


def run(args) -> int:
    """Execute one run (daily or backfill). Returns a process exit code."""
    config = _load_config()
    urls, newest = _gather_urls(args)
    if not urls:
        print("no new reposts with links; nothing to do")
        return 0

    print(f"processing {len(urls)} link(s)")
    enriched = process_urls(urls, args.model)

    # Split into genuinely new items (not yet archived) for the email.
    seen = store.load_seen_urls()
    new_items = [e for e in enriched if e.get("final_url") and e["final_url"] not in seen]

    OUT_DIR.mkdir(exist_ok=True)
    if args.dry_run:
        recommended = [e for e in enriched if e.get("recommended")]
        html_body = render_html(recommended or enriched)
        (OUT_DIR / "latest_digest.html").write_text(html_body, encoding="utf-8")
        print(f"[dry-run] {len(enriched)} processed, {len(recommended)} recommended; "
              f"wrote {OUT_DIR / 'latest_digest.html'} (no archive, draft, or push)")
        return 0

    # Archive everything new, then rebuild the site from the full archive.
    added = store.append_items(new_items)
    all_items = store.load_all_items()
    docs_dir = store.data_repo() / "docs"
    site_count = generate_site(all_items, docs_dir)
    print(f"archived +{added} (total {len(all_items)}); site has {site_count} items")

    if args.since and newest:
        from .capture import set_last_id

        set_last_id(newest)  # so the next daily run starts after the backfill

    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    if not args.no_push:
        _git_push(store.data_repo(), f"digest: +{added} items ({stamp})")

    # Email draft: this run's NEW recommended items only.
    recommended_new = [e for e in new_items if e.get("recommended")]
    recommended_new = recommended_new[:EMAIL_ITEM_CAP]
    if not recommended_new:
        print("no new recommended items; site updated, no draft created")
        return 0

    subj = subject(recommended_new)
    html_body = render_html(recommended_new)
    text_body = render_text(recommended_new)
    (OUT_DIR / "latest_digest.html").write_text(html_body, encoding="utf-8")

    if not args.no_draft:
        to_address = config.get("to_address", DEFAULT_TO)
        if config.get("draft_backend") == "gmail":
            from .draft import create_draft

            create_draft(to_address, subj, html_body, text_body)
        else:
            from .mailapp import create_draft

            create_draft(to_address, subj, text_body, html_path=str(OUT_DIR / "latest_digest.html"))
        print(f"created draft to {to_address}: {subj}")
        _maybe_push_phone(config, f"Morning reads ready: {len(recommended_new)} cool items")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reading digest from your X reposts.")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true", help="build locally only")
    common.add_argument("--no-state", action="store_true", help="do not advance the seen high-water mark")
    common.add_argument("--no-push", action="store_true", help="do not git push the data repo")
    common.add_argument("--no-draft", action="store_true", help="do not create the Mail draft")
    common.add_argument("--limit", type=int, default=80, help="timeline tweets to scan (daily)")
    common.add_argument("--model", default="sonnet", help="claude -p model alias")
    common.add_argument("--urls", nargs="*", help="explicit URLs, skipping capture")

    run_p = sub.add_parser("run", parents=[common], help="daily run")
    run_p.set_defaults(since=None)

    back_p = sub.add_parser("backfill", parents=[common], help="catch up since a date")
    back_p.add_argument("since", help="ISO cutoff date, for example 2026-05-01")

    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
