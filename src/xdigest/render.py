"""Render enriched repost items into an email digest (HTML and plain text).

The HTML uses a responsive, table-based layout adapted from Lee Munroe's
widely used responsive HTML email template (MIT), so it renders cleanly in
real mail clients instead of looking like a raw web page. Claims show the
reposted quote plus a who/what/why analysis; resources show the article text or
video summary. Every item carries two verdicts and "read more" links.
"""

from __future__ import annotations

import html

import markdown as md

from .links import read_more_url, reference_links

_GOOD = {"READ", "WATCH"}

_STYLE = """
body,table,td{font-family:Helvetica,Arial,sans-serif;}
body{background:#f4f5f6;margin:0;padding:0;font-size:16px;line-height:1.45;color:#06090f;-webkit-font-smoothing:antialiased;}
table{border-collapse:separate;width:100%;}
.body{background:#f4f5f6;width:100%;}
.container{margin:0 auto !important;max-width:640px;padding:24px;width:640px;}
.content{box-sizing:border-box;display:block;margin:0 auto;max-width:640px;}
.main{background:#ffffff;border:1px solid #eaebed;border-radius:16px;width:100%;}
.wrapper{box-sizing:border-box;padding:28px;}
h1{font-size:22px;margin:0 0 4px;font-weight:700;}
.sub{color:#6b7178;font-size:13px;margin:0 0 4px;}
.item{border-top:1px solid #eef0f2;padding:22px 0;}
.kind{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#fff;background:#9aa0a6;border-radius:5px;padding:2px 8px;}
.kind.claim{background:#5b3a8a;}.kind.video{background:#b1442c;}.kind.pdf{background:#7a5a1d;}.kind.article{background:#2e8b57;}
.date{color:#9aa0a6;font-size:12px;margin-left:8px;}
.title{font-size:18px;font-weight:700;margin:8px 0 4px;line-height:1.3;}
.title a{color:#0b5cad;text-decoration:none;}
.meta{color:#8b9097;font-size:13px;margin:0 0 10px;}
.badge{display:inline-block;font-size:12px;font-weight:700;padding:3px 10px;border-radius:20px;margin:0 8px 6px 0;}
.go{background:#e7f6ec;color:#1d7a3a;}.no{background:#f0f1f3;color:#8b9097;}
.gist{font-style:italic;color:#2b2f36;margin:10px 0;}
.ctx{color:#2b2f36;font-size:15px;margin:10px 0;}
.reason{color:#4b5158;font-size:13px;margin:3px 0;}
ul.summary{margin:8px 0;padding-left:20px;}ul.summary li{margin:4px 0;}
.body-text{margin-top:12px;padding-top:12px;border-top:1px dashed #e4e7ea;font-size:15px;color:#1c1f24;}
.body-text img{max-width:100%;}.body-text pre{background:#f6f8fa;padding:10px;overflow-x:auto;border-radius:8px;}
.readmore{margin:12px 0 0;font-size:13px;color:#6b7178;}
.readmore a{color:#0b5cad;text-decoration:none;}
.time{color:#9a6a00;font-size:12px;font-weight:700;}
.err{color:#b00;font-size:13px;}
.footer{padding-top:18px;text-align:center;color:#9aa0a6;font-size:12px;}
@media only screen and (max-width:640px){.container{width:100% !important;padding:12px !important;}.wrapper{padding:18px !important;}}
"""


def _badge(label: str, verdict: str | None) -> str:
    verdict = (verdict or "?").upper()
    cls = "go" if verdict in _GOOD else "no"
    return f'<span class="badge {cls}">{label}: {html.escape(verdict)}</span>'


def _counts(items: list[dict]) -> str:
    claims = sum(1 for i in items if i.get("type") == "claim")
    videos = sum(1 for i in items if i.get("type") != "claim" and i.get("kind") == "youtube")
    reads = len(items) - claims - videos
    return f"{len(items)} items ({reads} to read, {videos} videos, {claims} claims)"


def subject(items: list[dict]) -> str:
    """Build the email subject line."""
    return f"Your reposts digest: {_counts(items)}"


def _readmore_html(enrich: dict) -> str:
    """Build the 'read more' line from references and the dig-deeper query."""
    pieces = [f'<a href="{html.escape(url)}">{html.escape(label)}</a>'
              for label, url in reference_links(enrich.get("references"))]
    rm = read_more_url(enrich.get("read_more", ""))
    if rm:
        pieces.append(f'<a href="{html.escape(rm)}">search this topic</a>')
    if not pieces:
        return ""
    return f'<div class="readmore">Read more: {" &middot; ".join(pieces)}</div>'


def _verdict_block(enrich: dict) -> str:
    parts = ['<div>', _badge("Research", enrich.get("research_verdict")),
             _badge("General", enrich.get("general_verdict")), "</div>"]
    for label, key in (("Research", "research_reason"), ("General", "general_reason")):
        if enrich.get(key):
            parts.append(f'<div class="reason"><b>{label}:</b> {html.escape(enrich[key])}</div>')
    return "".join(parts)


def _render_item_html(item: dict) -> str:
    enrich = item.get("enrichment") or {}
    meta = item.get("meta") or {}
    url = html.escape(item.get("final_url") or item.get("source_url") or "")
    title = html.escape(item.get("title") or item.get("final_url") or "Link")
    author = item.get("author") or ""
    parts = ['<div class="item">']

    if item.get("type") == "claim":
        headline = html.escape(enrich.get("headline") or (item.get("repost_text") or "")[:90] or "Claim")
        parts.append('<span class="kind claim">Claim</span>')
        if item.get("date"):
            parts.append(f'<span class="date">{html.escape(item["date"][:10])}</span>')
        parts.append(f'<div class="title">{headline}</div>')
        if author:
            parts.append(f'<div class="meta">@{html.escape(author)}</div>')
        parts.append(_verdict_block(enrich))
        if item.get("repost_text"):
            parts.append(f'<div class="gist">&ldquo;{html.escape(item["repost_text"])}&rdquo;</div>')
        if enrich.get("context"):
            parts.append(f'<div class="ctx">{md.markdown(enrich["context"], extensions=["extra"])}</div>')
        if url:
            parts.append(f'<div class="reason">Linked: <a href="{url}">{title}</a></div>')
        parts.append(_readmore_html(enrich))

    elif item.get("kind") == "youtube":
        parts.append('<span class="kind video">Video</span>')
        if item.get("date"):
            parts.append(f'<span class="date">{html.escape(item["date"][:10])}</span>')
        parts.append(f'<div class="title"><a href="{url}">{title}</a></div>')
        bits = [b for b in (meta.get("channel"), meta.get("duration_human")) if b]
        parts.append(f'<div class="meta">{html.escape(" | ".join(bits))}</div>')
        parts.append(_verdict_block(enrich))
        if enrich.get("summary"):
            parts.append('<ul class="summary">')
            parts.extend(f"<li>{html.escape(str(b))}</li>" for b in enrich["summary"])
            parts.append("</ul>")
        if enrich.get("time_note"):
            parts.append(f'<div class="time">{html.escape(enrich["time_note"])}</div>')
        parts.append(_readmore_html(enrich))

    elif item.get("kind") == "article":
        is_pdf = bool(meta.get("pdf"))
        parts.append(f'<span class="kind {"pdf" if is_pdf else "article"}">{"PDF" if is_pdf else "Article"}</span>')
        if item.get("date"):
            parts.append(f'<span class="date">{html.escape(item["date"][:10])}</span>')
        parts.append(f'<div class="title"><a href="{url}">{title}</a></div>')
        bits = [meta.get("sitename")]
        if is_pdf and meta.get("pages"):
            bits.append(f'{meta["pages"]} pages')
        bits.append(f'{item.get("reading_minutes", 0)} min read')
        parts.append(f'<div class="meta">{html.escape(" | ".join(b for b in bits if b))}</div>')
        parts.append(_verdict_block(enrich))
        if enrich.get("gist"):
            parts.append(f'<div class="gist">{html.escape(enrich["gist"])}</div>')
        parts.append(_readmore_html(enrich))
        if item.get("text"):
            if meta.get("truncated"):
                parts.append(f'<div class="time">Showing the first part of a {meta.get("pages", "?")}-page PDF. '
                             f'Full document: <a href="{url}">{url}</a></div>')
            parts.append(f'<div class="body-text">{md.markdown(item["text"], extensions=["extra", "sane_lists"])}</div>')

    else:  # tweet / other fallback
        parts.append(f'<span class="kind">{html.escape(item.get("kind", "link"))}</span>')
        parts.append(f'<div class="title"><a href="{url}">{title}</a></div>')
        if item.get("error"):
            parts.append(f'<div class="err">{html.escape(item["error"])}</div>')

    parts.append("</div>")
    return "".join(parts)


def render_html(items: list[dict]) -> str:
    """Render the digest as a responsive HTML email."""
    header = (f"<h1>Your reposts digest</h1>"
              f"<p class='sub'>{_counts(items)}.</p>"
              f"<p class='sub'>Two verdicts per item: research relevance and general value.</p>")
    body = "".join(_render_item_html(i) for i in items)
    return (
        '<!doctype html><html lang="en"><head>'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
        f"<style>{_STYLE}</style></head><body>"
        '<table role="presentation" class="body"><tr><td>&nbsp;</td>'
        '<td class="container"><div class="content">'
        '<table role="presentation" class="main"><tr><td class="wrapper">'
        f"{header}{body}"
        "</td></tr></table>"
        '<div class="footer">x-reader-digest</div>'
        "</div></td><td>&nbsp;</td></tr></table></body></html>"
    )


def render_text(items: list[dict]) -> str:
    """Render a plain-text fallback version of the digest."""
    lines = [f"YOUR REPOSTS DIGEST: {_counts(items)}", ""]
    for item in items:
        enrich = item.get("enrichment") or {}
        lines.append("-" * 60)
        if item.get("type") == "claim":
            lines.append(f"[CLAIM] {enrich.get('headline', '') or (item.get('repost_text', '')[:80])}")
            if item.get("author"):
                lines.append(f"@{item['author']}")
            lines.append(f"Research: {enrich.get('research_verdict', '?')} | General: {enrich.get('general_verdict', '?')}")
            if item.get("repost_text"):
                lines.append(f'Reposted: "{item["repost_text"]}"')
            if enrich.get("context"):
                lines.append("")
                lines.append(enrich["context"])
        else:
            lines.append(f"[{item['kind'].upper()}] {item.get('title', '')}")
            lines.append(item.get("final_url", ""))
            lines.append(f"Research: {enrich.get('research_verdict', '?')} | General: {enrich.get('general_verdict', '?')}")
            if enrich.get("gist"):
                lines.append(f"Gist: {enrich['gist']}")
            for bullet in enrich.get("summary", []):
                lines.append(f"  - {bullet}")
            if enrich.get("time_note"):
                lines.append(enrich["time_note"])

        refs = reference_links(enrich.get("references"))
        rm = read_more_url(enrich.get("read_more", ""))
        if refs or rm:
            lines.append("Read more: " + " | ".join([f"{label} {url}" for label, url in refs] + ([rm] if rm else [])))
        if item.get("type") != "claim" and item.get("kind") == "article" and item.get("text"):
            lines.append("")
            lines.append(item["text"])
        lines.append("")
    return "\n".join(lines)
