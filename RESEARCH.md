# X reposts and bookmarks to a calm Kindle read: what to actually do

## 1. TL;DR and the single recommended path

There is no single, still-maintained tool in 2026 that takes "your X reposts" (or your bookmarks) and delivers them to a Kindle out of the box. Every working solution is a two-stage assembly: (1) get the content out of X, which is the hard and fragile half, and (2) turn it into an EPUB and deliver it, which is the easy and healthy half that you already own through `paper2kindle`. The good news is that reposts, the thing you specifically asked about, are the easy case: they are public, they sit in the free official data archive, and any profile-timeline scraper returns them without a paid API. Bookmarks are the hard case and need either the now-metered X API or a cookie-riding browser tool.

Recommended path for you: reuse what you have. Capture with `prinsss/twitter-web-exporter` (plus the free official archive to clear the backlog), build a sectioned EPUB "periodical" with a Calibre recipe, send it with your existing `paper2kindle` local-file path (Gmail OAuth to your `@kindle.com` address), schedule it nightly on a launchd timer exactly like `tender-watch`, and use `push-to-phone` as the "morning digest is ready" ping and phone fallback. This costs nothing beyond what you run, handles your historical backlog (which the hosted tools cannot retroactively grab), and keeps the whole thing in the Python plus CLI plus launchd shape you already maintain.

## 2. The hard truth about getting data out of X in 2026

The three things you might want behave very differently. Treat them as three separate problems, not one.

**Reposts (your retweets and quote tweets): easy, public, no paid API needed.** Your reposts live in `tweets.js` inside the free official "Download an archive of your data" export (Settings, Your account, Download an archive of your data), and they also appear in any scrape of your public profile timeline because the profile timeline includes retweets. Every session scraper returns them: `twscrape` (`api.user_tweets`), `twikit` (`get_user_tweets(tweet_type='Tweets')`), `gallery-dl` on a profile URL, and the `prinsss` userscript on your own timeline. The official archive is the zero-code, zero-risk way to grab them, with one catch: it is a one-shot dump, rate-limited to roughly one request per 30 days, and can take a day to generate. Good for a backlog flush, not for a daily feed.

**Likes: medium, in the archive but thin.** Likes are in the same free archive as `like.js`. Verified field set as of 2026 is `tweetId`, `fullText`, and `expandedUrl`, with no created_at or timestamp at all, so you cannot sort your likes chronologically from the archive. Scrapers and the `prinsss` userscript can also pull likes. Most third-party "bookmark" SaaS tools do not sync likes.

**Bookmarks: genuinely hard, and this is where the friction is real.** Bookmarks are private, they are never in the official archive, and there are only three routes:

- The official X API v2 (`GET /2/users/:id/bookmarks`), which requires an OAuth 2.0 PKCE user-context token with the `bookmark.read` scope. App-only Bearer tokens cannot read bookmarks. This is clean but no longer free: as of 6 February 2026 new developers default to metered pay-per-use with no general free tier, and as of 1 June 2026 even legacy Basic subscribers are being auto-migrated to pay-per-use. There is an "Owned Reads" category at an announced $0.001 per resource (effective 20 April 2026) that covers your own posts, bookmarks, followers, and lists. Honest caveat from a developer-forum bug report: the $0.001 owned-reads rate may not actually be applied to the bookmarks endpoint, which is reportedly still billing at $0.005 per resource. Verify in the X Developer Console before assuming the cheap rate.
- A browser-session tool that rides your logged-in cookies and reads X's internal GraphQL: `prinsss/twitter-web-exporter`, `tweetxvault`, `gallery-dl` with `--cookies-from-browser`, `twscrape`, or `twikit`. Free, but cat-and-mouse: these break every few weeks when X rotates GraphQL IDs, and they carry account-action risk. The `prinsss` userscript is the lowest-detection option because it passively intercepts the GraphQL responses the web app already loads rather than issuing its own API calls.
- A SaaS (Readwise via the official API, Dewey or TweetSmash via a Chrome extension). All are subscriptions, and Readwise's X bookmark sync is forward-only and labeled experimental: it imports only bookmarks saved after you enable it, so it cannot retroactively pull your existing backlog.

Two dead ends to stop considering: `snscrape` is practically dead for X (it relied on guest access that X locked behind a login wall in mid-2023, and the repo has had no commits since June 2023). Public Nitter and RSSHub Twitter feeds are fragile: most public Nitter instances are down, and RSSHub's `/twitter/user` route now needs a logged-in cookie and was widely reported returning empty output through 2025. Pocket and Omnivore are both fully shut down (Pocket data deleted after 12 November 2025, Omnivore offline since November 2024), so ignore any guide that routes through them.

Bottom line: solve reposts first with the free archive, accept that bookmarks need a cookie-scraper (with maintenance budget) or a metered API call, and do not expect a "free, no-login, reliable" X feed, because none survive.

## 3. Buy vs build

**The fastest hosted path: Readwise Reader, with an honest gap.** You already use Reader, and it has the cleanest native Send-to-Kindle of anything here: add your `@kindle.com` address under Integrations and toggle Automatic Delivery to daily or weekly, and it builds an EPUB and emails it to your Kindle. But Reader does not solve your stated problem out of the box. It has no "your reposts" feed, and its X bookmark sync is forward-only and experimental, so it cannot grab your existing reposts or bookmark backlog. The clean Reader-native pattern is a behavior change: curate a public Twitter List, subscribe to that List as an RSS feed in Reader (Reader supports public Lists as feeds), and enable the daily Kindle digest. That is genuinely zero-maintenance and arguably fixes the deeper issue (reposting into a void and never reading), at roughly $9.99/month billed annually, which you may already pay. Buy this if you are willing to replace "repost and forget" with "save to a List and read the digest," and if you do not care about retroactively reading the years of reposts already sitting in your history.

**The self-hosted build: reuse paper2kindle plus Calibre plus a capture tool plus launchd.** This is the right call for you specifically, for four reasons that match your profile and your actual ask. First, your stated need includes a backlog of historical reposts and bookmarks, which Reader's forward-only sync structurally cannot retrieve, but the official archive plus a one-time scraper run can. Second, you already own the entire delivery leg: `paper2kindle` is configured at `~/.paper2kindle` with `kindle_email`, `sender_email`, and Gmail OAuth2, and it already has a local-file send path, so the "easy half" is done. Third, you already run scheduled local pipelines on launchd (`com.amit.tenderwatch.plist`), so a nightly digest job fits your habits exactly. Fourth, it is free, fully under your control, reproducible as scripts, and maintainable in Python, which matches your quality bar over the cheapest path. The cost is maintenance: cookie scrapers break periodically.

Recommendation: build the pipeline as your primary system, and optionally layer Reader's List-to-Kindle digest on top as a no-effort going-forward channel. They are complementary, not redundant: the build clears and curates the backlog, Reader handles the steady drip if you adopt the List habit.

## 4. Comparison of the most relevant tools

| Tool | X path | Kindle path | Open source / self-host | Cost | 2026 status | Fit for Amit |
|---|---|---|---|---|---|---|
| Official "Download your data" archive | Reposts (tweets.js) + likes (like.js); no bookmarks | None (raw ZIP, convert yourself) | n/a (X feature) | Free | Active; one-shot, ~1 per 30 days | High for backlog flush of reposts and likes |
| prinsss/twitter-web-exporter (userscript) | Bookmarks, likes, reposts, lists via GraphQL interception | None native; HTML/JSON is clean EPUB base | Yes (MIT), browser-side only | Free | Active, v1.4.0 Feb 2026, ~2.6k stars | High: lowest-detection bookmark and repost capture |
| vladkens/twscrape | Bookmarks, reposts (user tweets), likes via cookie sessions | None (returns JSON) | Yes (MIT), self-host | Free | Active, v0.19.1 Jun 2026 | High if he wants scripted, scheduled capture |
| lhl/tweetxvault | Bookmarks + likes + authored tweets to local DB, HTML export | None native; clean HTML export | Yes, self-host (macOS supported) | Free | Active, v0.2.4 Apr 2026, small project | Medium: purpose-built local bookmark archive |
| X API v2 (Owned Reads) | Bookmarks (OAuth2 PKCE + bookmark.read), reposts, likes | None (raw JSON) | No (client libs OSS) | Pay-per-use; owned reads ~$0.001/resource (verify; bookmarks may bill $0.005) | Active; pricing volatile, no free tier | Low-medium: clean but metered and OAuth overhead |
| Thytu/XRSS or RSSHub | Reposts as RSS (include_retweets / includeRts), cookie auth | None (RSS, pair with Calibre) | Yes, self-host | Free | XRSS small/niche; RSSHub route flaky | Low-medium: reposts RSS, but fragile |
| Readwise Reader | Forward-only bookmark sync (experimental); public Lists as RSS; no reposts feed | Native daily/weekly EPUB Kindle digest | No (SaaS) | ~$9.99/mo annual | Active, well-maintained | Medium-high if he adopts the List habit; cannot grab backlog |
| Calibre "Fetch news" + ebook-convert | None (consumes a feed/file the capture stage produces) | Best-in-class: true periodical (masthead, sections, nav TOC), auto-email | Yes (GPL-3), self-host | Free | Active, manual 9.x in 2026 | High: the EPUB-periodical backbone |
| bookfere/Calibre-News-Delivery | None (runs Calibre recipes) | Emails periodical to @kindle.com on a cron | Yes (GPL-3), GitHub Actions | Free | Active, small (~53 stars) | Medium: serverless scheduling if he avoids a local launchd job |
| nikhil1raghav/kindle-send | None (ingests URLs/feeds) | Builds EPUB and emails to Kindle, cron-friendly | Yes (AGPL-3), self-host | Free | Works; low activity (last release 2023) | Medium: reference for the delivery leg he already has |
| paper2kindle (his own) | None (delivery only) | Gmail OAuth send to @kindle.com; local-file path | Yes (his repo) | Free | His, configured and working | Core reused component: the send leg is solved |

## 5. Recommended architecture for Amit

A four-stage pipeline that reuses `paper2kindle` and launchd and produces a proper Kindle periodical, not a flat blob.

**Stage 1, capture (the only new code worth writing).**
- Backlog, one time: request the official archive for all reposts and likes (free, no risk), and run the `prinsss/twitter-web-exporter` userscript once over your Bookmarks and Likes pages to dump JSON/HTML. This clears years of history that no hosted tool can retroactively reach.
- Recurring: pick one of two. Lowest-detection and lowest-effort is keeping the `prinsss` userscript and exporting on demand. Fully scripted and schedulable is `twscrape` (MIT, current, `api.bookmarks(...)` and `api.user_tweets(...)`) reading your bookmarks and your profile timeline (which includes reposts) into JSON. Use your real account cookies for bookmarks (they are tied to your account), accept the read-only risk, and keep the export read-only.

**Stage 2, build a periodical (Calibre, the single biggest quality lever).** Write a short Calibre `.recipe` (about 10 to 15 lines of Python) that reads the Stage 1 JSON/HTML and emits sections: "Bookmarks," "Reposts," and optionally "Likes." This is what gives you the newspaper UX on the Kindle: a masthead, named sections, and a navigable table of contents, so you open the issue, see an article list, tap one, and "back" returns you to the section instead of one endless scroll. Bound the issue (`oldest_article` for a true daily, `max_articles_per_feed`) so the morning read is finite and finishable. Emit EPUB or AZW3, never PDF, so the text reflows on the e-ink screen. Run it headless with `ebook-convert myrecipe.recipe digest.epub`. Calibre recipe reference: https://manual.calibre-ebook.com/news_recipe.html

**Stage 3, deliver (reuse paper2kindle, zero new work).** Hand the generated `digest.epub` to your existing `paper2kindle` local-file send path. It already sends to your `@kindle.com` via Gmail OAuth from your approved `sender_email`. One check: confirm that exact Gmail sender is on your Amazon Approved Personal Document Email List (Manage Your Content and Devices, Preferences, Personal Document Settings), because since 1 April 2025 Amazon requires full sender addresses, not domain-only entries. Send-to-Kindle accepts EPUB (it transcodes to its own KF8/KFX on device); the 50 MB per-email cap is irrelevant for a text digest.

**Stage 4, schedule and notify (launchd plus push-to-phone).** Wrap stages 1 to 3 in one script and run it on a launchd timer overnight, modeled on `com.amit.tenderwatch.plist`, timed so the issue is built and emailed a couple of hours before you wake; the Kindle pulls it on the next Wi-Fi sync. Then fire `push-to-phone` with an ntfy notification ("morning digest ready, N bookmarks plus M reposts"). The phone is your fallback read: if the Kindle delivery ever fails, the same EPUB opens in the Kindle phone app, and the push gives you a tappable nudge so the digest does not silently sit unread. This deliberately replaces "open X and scroll" with "tap a notification, read a bounded issue."

Optional zero-maintenance overlay: separately, turn on Readwise Reader's daily Kindle digest fed by a curated public Twitter List. It runs entirely on its own and gives you a second, effortless channel for things you deliberately save going forward, while the build pipeline owns the backlog and your bookmarks.

## 6. Fastest win for tomorrow morning

You can start reading your backlog tonight with almost no code:

1. Open X on desktop, install the `prinsss/twitter-web-exporter` userscript (Tampermonkey), go to your Bookmarks page, and export to HTML. This is the single highest-value 10-minute action because it captures the hard case (private bookmarks) immediately.
2. Open Calibre, drag the exported HTML in, and convert to EPUB (or just keep the HTML).
3. Run `paper2kindle` on that file to send it to your Kindle, or, even simpler for tonight, attach the EPUB to an email from your approved Gmail sender to your `@kindle.com` address.

That gets your actual bookmark backlog onto the Kindle tonight as one readable document, with zero new scripts. The polished sectioned-periodical recipe, the launchd schedule, and the push ping are the upgrade you build over the next few evenings once the basic flow has proven itself.

## 7. Reusable and forkable repos

Prefer adopting these over writing net-new code. URLs included so you are not starting from scratch.

- Your own delivery leg, reuse as-is: `AmitSubhash/paper2kindle` (https://github.com/AmitSubhash/paper2kindle). Already does Gmail OAuth send to `@kindle.com` and has a local-file path. This is your Stage 3.
- X capture, primary: `prinsss/twitter-web-exporter` (https://github.com/prinsss/twitter-web-exporter), MIT, v1.4.0, exports bookmarks, likes, reposts, lists to JSON/CSV/HTML by intercepting GraphQL. Lowest detection.
- X capture, scripted alternative: `vladkens/twscrape` (https://github.com/vladkens/twscrape), MIT, current (v0.19.1, June 2026), good for a scheduled job.
- X capture, purpose-built bookmark archive: `lhl/tweetxvault` (https://github.com/lhl/tweetxvault), local DB plus clean HTML export, macOS supported.
- EPUB periodical engine: Calibre "Fetch news" recipe system (https://manual.calibre-ebook.com/news_recipe.html). This is your Stage 2 and the main quality lever.
- Serverless scheduling alternative to launchd: `bookfere/Calibre-News-Delivery` (https://github.com/bookfere/Calibre-News-Delivery), GPL-3, runs Calibre in GitHub Actions on a cron and emails the issue to your Kindle. Use this only if you would rather not keep a local machine awake; small project, check recent commits first.
- Delivery-leg reference if you ever rebuild it: `nikhil1raghav/kindle-send` (https://github.com/nikhil1raghav/kindle-send), AGPL-3, Go CLI that builds EPUB and emails to Kindle, and the clean write-up at https://olano.dev/blog/from-rss-to-my-kindle/ (Readability to EPUB to SMTP). You will not need these since `paper2kindle` already covers it, but they are the canonical patterns.
- Reposts-as-RSS, only if you go the Reader/RSS route: `Thytu/XRSS` (https://github.com/Thytu/XRSS) with `include_retweets`, or `DIYgod/RSSHub` (https://github.com/DIYgod/RSSHub) `/twitter/user` with `includeRts`. Both need a logged-in cookie and are fragile; treat as secondary.

## 8. Open questions and risks

- Cookie-scraper fragility: `prinsss`, `twscrape`, `tweetxvault`, RSSHub, and XRSS all ride X's internal GraphQL and break every few weeks when X rotates IDs or guest tokens. Budget recurring maintenance, and prefer the `prinsss` userscript because passive interception is the least likely to trip detection.
- Account risk on bookmarks: bookmarks are tied to your real account, so you must use your real cookies to read them; there is no throwaway-account workaround for bookmarks (unlike public reposts). Keep all access strictly read-only.
- X API pricing is volatile and partly unverified: the $0.001 "owned reads" rate is announced but a developer-forum bug report says bookmarks still bill at $0.005. If you ever consider the API route, confirm the actual billed rate in the Developer Console first.
- Archive limits: the official "Download your data" export is one-shot, rate-limited to roughly one per 30 days, and excludes bookmarks entirely. `like.js` has no timestamps, so you cannot order likes chronologically from it.
- Send-to-Kindle gate: confirm your `paper2kindle` Gmail `sender_email` is on Amazon's Approved Personal Document Email List as a full address (required since 1 April 2025). Send EPUB or AZW3, not PDF, for reflow. If your Kindle predates 2013, note Amazon is phasing out wireless Send-to-Kindle for those models in 2026 (likely irrelevant to you, but worth a glance).
- Readwise gap: its X bookmark sync is forward-only and experimental, so it will not retroactively import your backlog, and it has no native reposts feed. Do not expect Reader alone to satisfy the stated ask.
- Secondary-source caveats from the research: several Amazon and X help pages returned 403/503 to automated fetches, so a few exact format and pricing facts are corroborated from 2026 third-party sources rather than first-party pages. The load-bearing facts (bookmarks excluded from the archive, EPUB accepted, MOBI dropped, no free X API tier) are multiply corroborated and safe to act on; re-confirm exact cents and device cutoffs against the primary pages before quoting them.
