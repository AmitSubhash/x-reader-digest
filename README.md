# x-reader-digest

Turn your X (Twitter) reposts into a calm email digest you can read after you
wake up, instead of scrolling X. Each reposted link is followed and worked on:

- **Articles** are pulled in full (clean readable text inline), plus a one-line
  gist and two "worth your time" labels.
- **Videos** get a short summary, a watch-or-skip call, and a runtime-vs-payoff
  note, so you do not gamble 20 minutes on a video blind.

Every item carries two verdicts side by side: **research relevance** (DOT,
fNIRS, ML for medical imaging, inverse problems) and **general value**.

The result is delivered as a **Gmail draft to yourself** (you tap send, or just
read the draft), built on a launchd timer each morning.

## How it works

```
capture (twscrape + Brave cookies)
   ->  extract (trafilatura article / pypdf PDF / yt-dlp + transcript)
   ->  summarize (claude -p, sonnet, no API key)
   ->  render (HTML email)  ->  draft (Mail.app via AppleScript, or Gmail)
```

No paid X API and no LLM API key: reposts are public timeline data read with
your own Brave session, and summaries run through your local `claude -p`
subscription. PDFs (papers, lecture notes, books) are extracted too; long ones
are inlined in part and linked in full.

## One-time setup

1. **Delivery (Mail.app, default).** Drafts are saved to your `Exchange`
   account's Drafts via AppleScript and never sent. The only setup is allowing
   the process to control Mail the first time (a macOS prompt; click OK). No
   account auth. To draft from a different Mail account, set its name in config.
   (Optional alternative: Gmail drafts via `draft_backend: "gmail"` in config
   plus `PYTHONPATH=src .venv/bin/python -m xdigest.draft auth`.)

2. **X session via Brave.** Capture reads your live X cookies from the local
   Brave browser on every run, so there is nothing to paste and nothing to
   expire. The only setup is authorizing the Keychain once: run the line below
   and click **Always Allow** on the dialog (this lets the scheduled job read
   Brave's cookie key unattended). It prints cookie shapes, no secrets.
   ```
   PYTHONPATH=src .venv/bin/python -m xdigest.brave_cookies
   ```
   Stay logged into X in Brave's Default profile and capture keeps working.

3. **Optional config** at `~/.config/xdigest/config.json`:
   ```json
   { "to_address": "atsubhas@iu.edu" }
   ```

## Run it

```
# build from your new reposts and create the Gmail draft
PYTHONPATH=src .venv/bin/python -m xdigest.pipeline run

# preview only: write out/latest_digest.html, no draft, no state change
PYTHONPATH=src .venv/bin/python -m xdigest.pipeline run --dry-run

# test on explicit links, skipping capture
PYTHONPATH=src .venv/bin/python -m xdigest.pipeline run --dry-run --urls <url1> <url2>
```

## Schedule (launchd)

```
cp launchd/com.amit.xdigest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.amit.xdigest.plist
```

Runs daily at 06:30. Edit `StartCalendarInterval` to change the time. Logs land
in `logs/`.

## Notes

- Capture refreshes cookies from Brave each run, so it survives cookie
  expiry. If `fetch` ever returns nothing, confirm you are still logged into X
  in Brave; if X changed its internals, bump the `twscrape` version.
- Verdicts and summaries are written by `claude -p --model sonnet`; no em dashes
  by instruction.
