"""Render enriched repost items into an email digest (HTML and plain text).

Articles are shown with their full readable text inline so the email is the
content. Videos are shown as a summary plus two verdict badges, with the link
to watch. Both carry research and general verdicts side by side.
"""

from __future__ import annotations

import html
from typing import Optional

import markdown as md

_GOOD = {"READ", "WATCH"}

_STYLE = """
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
line-height:1.55;color:#1a1a1a;max-width:680px;margin:0 auto;padding:16px;}
h1{font-size:20px;margin:0 0 4px;} .sub{color:#666;font-size:13px;margin:0 0 20px;}
.item{border-top:1px solid #e6e6e6;padding:22px 0;}
.kind{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#888;}
.title{font-size:17px;font-weight:600;margin:2px 0 6px;}
.title a{color:#0a4d8c;text-decoration:none;} .meta{color:#777;font-size:13px;margin:0 0 10px;}
.badges{margin:8px 0 12px;}
.badge{display:inline-block;font-size:12px;font-weight:600;padding:3px 9px;border-radius:5px;margin-right:8px;}
.go{background:#e6f4ea;color:#1d7a3a;} .no{background:#f0f0f0;color:#777;}
.reason{color:#444;font-size:13px;margin:3px 0;}
.gist{font-style:italic;color:#333;margin:8px 0;}
ul.summary{margin:8px 0;padding-left:20px;} ul.summary li{margin:4px 0;}
.article-body{margin-top:14px;padding-top:12px;border-top:1px dashed #ddd;font-size:15px;}
.article-body img{max-width:100%;} .article-body pre{background:#f6f8fa;padding:10px;overflow-x:auto;border-radius:6px;}
.time{color:#9a6a00;font-size:12px;font-weight:600;} .err{color:#b00;font-size:13px;}
"""


def _badge(label: str, verdict: Optional[str]) -> str:
    verdict = (verdict or "?").upper()
    cls = "go" if verdict in _GOOD else "no"
    return f'<span class="badge {cls}">{label}: {html.escape(verdict)}</span>'


def _counts(items: list[dict]) -> str:
    articles = sum(1 for i in items if i["kind"] == "article")
    videos = sum(1 for i in items if i["kind"] == "youtube")
    return f"{len(items)} items ({articles} articles, {videos} videos)"


def subject(items: list[dict]) -> str:
    """Build the email subject line."""
    return f"Your reposts digest: {_counts(items)}"


def _render_item_html(item: dict) -> str:
    enrich = item.get("enrichment") or {}
    title = html.escape(item.get("title") or item.get("final_url") or "Link")
    url = html.escape(item.get("final_url") or item.get("source_url") or "")
    parts = ['<div class="item">']

    if item["kind"] == "youtube":
        meta = item.get("meta") or {}
        parts.append('<div class="kind">Video</div>')
        parts.append(f'<div class="title"><a href="{url}">{title}</a></div>')
        bits = [b for b in (meta.get("channel"), meta.get("duration_human")) if b]
        parts.append(f'<div class="meta">{html.escape(" | ".join(bits))}</div>')
        parts.append('<div class="badges">')
        parts.append(_badge("Research", enrich.get("research_verdict")))
        parts.append(_badge("General", enrich.get("general_verdict")))
        parts.append("</div>")
        if enrich.get("summary"):
            parts.append('<ul class="summary">')
            parts.extend(f"<li>{html.escape(str(b))}</li>" for b in enrich["summary"])
            parts.append("</ul>")
        for label, key in (("Research", "research_reason"), ("General", "general_reason")):
            if enrich.get(key):
                parts.append(f'<div class="reason"><b>{label}:</b> {html.escape(enrich[key])}</div>')
        if enrich.get("time_note"):
            parts.append(f'<div class="time">{html.escape(enrich["time_note"])}</div>')

    elif item["kind"] == "article":
        meta = item.get("meta") or {}
        is_pdf = bool(meta.get("pdf"))
        parts.append(f'<div class="kind">{"PDF" if is_pdf else "Article"}</div>')
        parts.append(f'<div class="title"><a href="{url}">{title}</a></div>')
        bits = [meta.get("sitename")]
        if is_pdf and meta.get("pages"):
            bits.append(f'{meta["pages"]} pages')
        bits.append(f'{item.get("reading_minutes", 0)} min read')
        parts.append(f'<div class="meta">{html.escape(" | ".join(b for b in bits if b))}</div>')
        parts.append('<div class="badges">')
        parts.append(_badge("Research", enrich.get("research_verdict")))
        parts.append(_badge("General", enrich.get("general_verdict")))
        parts.append("</div>")
        if enrich.get("gist"):
            parts.append(f'<div class="gist">{html.escape(enrich["gist"])}</div>')
        for label, key in (("Research", "research_reason"), ("General", "general_reason")):
            if enrich.get(key):
                parts.append(f'<div class="reason"><b>{label}:</b> {html.escape(enrich[key])}</div>')
        if item.get("text"):
            if meta.get("truncated"):
                parts.append(
                    f'<div class="time">Showing the first part of a {meta.get("pages", "?")}-page PDF. '
                    f'Full document: <a href="{url}">{url}</a></div>'
                )
            body_html = md.markdown(item["text"], extensions=["extra", "sane_lists"])
            parts.append(f'<div class="article-body">{body_html}</div>')
        elif item.get("enrich_error") or item.get("error"):
            parts.append(f'<div class="err">Could not extract full text: {html.escape(item.get("error") or "")}</div>')

    else:  # tweet / other
        parts.append(f'<div class="kind">{html.escape(item["kind"])}</div>')
        parts.append(f'<div class="title"><a href="{url}">{title}</a></div>')
        if item.get("error"):
            parts.append(f'<div class="err">{html.escape(item["error"])}</div>')

    parts.append("</div>")
    return "\n".join(parts)


def render_html(items: list[dict]) -> str:
    """Render the full digest as a standalone HTML document."""
    body = "\n".join(_render_item_html(i) for i in items)
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<style>{_STYLE}</style></head><body>"
        f"<h1>Your reposts digest</h1>"
        f"<p class='sub'>{_counts(items)}. Read verdicts are research relevance and general value, side by side.</p>"
        f"{body}</body></html>"
    )


def render_text(items: list[dict]) -> str:
    """Render a plain-text fallback version of the digest."""
    lines = [f"YOUR REPOSTS DIGEST: {_counts(items)}", ""]
    for item in items:
        enrich = item.get("enrichment") or {}
        lines.append("-" * 60)
        lines.append(f"[{item['kind'].upper()}] {item.get('title', '')}")
        lines.append(item.get("final_url", ""))
        if item["kind"] != "tweet":
            lines.append(
                f"Research: {enrich.get('research_verdict', '?')} | "
                f"General: {enrich.get('general_verdict', '?')}"
            )
        if enrich.get("gist"):
            lines.append(f"Gist: {enrich['gist']}")
        for bullet in enrich.get("summary", []):
            lines.append(f"  - {bullet}")
        if enrich.get("time_note"):
            lines.append(enrich["time_note"])
        if item["kind"] == "article" and item.get("text"):
            lines.append("")
            lines.append(item["text"])
        lines.append("")
    return "\n".join(lines)
