<div align="center">

<img src="assets/banner.svg" alt="x-reader-digest" width="100%">

<p>
  <img alt="license" src="https://img.shields.io/badge/license-MIT-6ea8fe">
  <img alt="python" src="https://img.shields.io/badge/python-3.11%2B-6ea8fe">
  <img alt="llm" src="https://img.shields.io/badge/LLM-claude%20--p%20(no%20API%20key)-b18cff">
  <img alt="delivery" src="https://img.shields.io/badge/delivery-email%20%2B%20web-2e8b57">
</p>

<b>Turn your X reposts into a calm reading digest you actually get through.</b><br>
Articles delivered in full. Videos triaged with a watch-or-skip call. Opinions and
claims explained (who is referenced, why it was said). Ranked by your taste, sent
to your inbox each morning, and browsable on a filterable site.

</div>

---

## Why

You repost a lot on X and never get back to it. This follows each reposted link
and does the work so reading is calm, not a scroll:

- **Articles** are pulled in full (clean text inline), plus a one-line gist.
- **Videos** get a transcript-based summary and a watch-or-skip call, so you do
  not gamble 20 minutes blind. Lectures get a thorough summary.
- **Claims and opinions** (a tweet with no article, like "study Tero Karras's
  papers") get a who/what/why explanation and links to dig deeper.

Every item carries two verdicts, research relevance and general value, and a
**read-more** row built from the people, papers, and concepts it mentions.

## How it works

```
capture (twscrape + Brave cookies, retweets only)
   ->  extract (trafilatura article / pypdf PDF / yt-dlp + transcript video)
   ->  analyze (claude -p, sonnet: resource summary or claim explanation, verdicts, score)
   ->  archive (JSONL, incremental)  ->  rank by taste
   ->  render (responsive email)  ->  send / draft  ->  rebuild filterable site  ->  push
```

No paid X API and no LLM API key: reposts are public timeline data read with your
own Brave session, and analysis runs through your local `claude -p` subscription.

## Your taste

[`TASTE.md`](TASTE.md) is the heart of the feed. Edit it in plain prose to say
what you love, what to always surface, what to skip, and how to score. The digest
reads it to triage every repost and **rank your daily feed**. Keep a private
taste by copying it to `~/.config/xdigest/taste.md` (that path wins).

## One-time setup

1. **Install**
   ```
   uv venv .venv && uv pip install -r requirements.txt
   ```
2. **X session via Brave.** Capture reads your live X cookies from Brave each run
   (nothing to paste, nothing to expire). Authorize the Keychain once and click
   Always Allow:
   ```
   PYTHONPATH=src .venv/bin/python -m xdigest.brave_cookies
   ```
3. **Delivery.** Set `~/.config/xdigest/config.json`:
   ```json
   { "to_address": "you@example.com", "send": true, "data_repo": "/path/to/x-reader-digest-data" }
   ```
   `send: true` sends to yourself via the Gmail API (reuses a paper2kindle-style
   token); omit it to save a Mail.app draft instead.

## Run it

```
PYTHONPATH=src .venv/bin/python -m xdigest.pipeline run            # daily
PYTHONPATH=src .venv/bin/python -m xdigest.pipeline run --dry-run  # preview, no send
PYTHONPATH=src .venv/bin/python -m xdigest.pipeline backfill 2026-05-01   # catch up (resumable)
```

## Data and website

Processed items are archived as JSONL in a separate **private** data repo, and a
filterable site is regenerated from it each run (`docs/index.html`): ranked
newest-and-best first, filter by Recommended / Skipped / Claims / Articles /
Videos / PDFs, with search. Enable GitHub Pages on `docs/` to host it.

## Schedule

```
cp launchd/com.amit.xdigest.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.amit.xdigest.plist
```

Runs daily at 06:00; the reading is waiting when you wake.

## Notes

- Retweets only (quote-tweets excluded). Book PDFs (over 30 pages) and junk hosts
  are skipped. Code snippets are stripped from article bodies.
- Cookie-based capture rides X's internals; if `fetch` goes empty, confirm you
  are still logged into X in Brave.
- No em dashes, by instruction.
