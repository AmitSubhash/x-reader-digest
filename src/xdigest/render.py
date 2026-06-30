"""Render enriched repost items into an email digest (HTML and plain text).

The HTML is a wide, generously sized, table-based layout with inline styles
(structure adapted from Ted Goas's Cerberus responsive email patterns, MIT), so
it renders large and clean in real mail clients. Claims show the reposted quote
plus a who/what/why analysis; resources show the article text or video summary.
Code snippets are stripped from article bodies. Every item carries two verdicts
and "read more" links.
"""

from __future__ import annotations

import html
import re

import markdown as md

from .links import read_more_url, reference_links

_GOOD = {"READ", "WATCH"}
_FONT = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
_KIND_BG = {"claim": "#5b3a8a", "video": "#b1442c", "pdf": "#7a5a1d", "article": "#2e8b57"}

_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_CODE_PRE = re.compile(r"<pre\b.*?</pre>", re.DOTALL | re.IGNORECASE)
_CODE_INDENT = re.compile(r"(?m)^(?: {4}|\t).*$")


def _strip_code(text: str) -> str:
    """Remove fenced and indented code blocks from markdown text."""
    text = _CODE_FENCE.sub("", text or "")
    text = _CODE_INDENT.sub("", text)
    return text


def _badge(label: str, verdict: str | None) -> str:
    verdict = (verdict or "?").upper()
    good = verdict in _GOOD
    bg, fg = ("#e7f6ec", "#1d7a3a") if good else ("#eef0f2", "#8b9097")
    return (f'<span style="display:inline-block;{_FONT}font-size:13px;font-weight:700;'
            f'padding:5px 13px;border-radius:20px;margin:0 8px 8px 0;background:{bg};color:{fg};">'
            f'{label}: {html.escape(verdict)}</span>')


def _kind_badge(kind: str, label: str) -> str:
    bg = _KIND_BG.get(kind, "#9aa0a6")
    return (f'<span style="display:inline-block;{_FONT}font-size:12px;font-weight:700;'
            f'letter-spacing:.06em;text-transform:uppercase;color:#fff;background:{bg};'
            f'border-radius:5px;padding:4px 10px;">{html.escape(label)}</span>')


def _title(url: str, text: str) -> str:
    inner = (f'<a href="{url}" style="color:#0b5cad;text-decoration:none;">{text}</a>'
             if url else f'<span style="color:#11151a;">{text}</span>')
    return f'<div style="{_FONT}font-size:21px;font-weight:700;line-height:1.35;margin:14px 0 4px;">{inner}</div>'


def _meta(text: str) -> str:
    return f'<div style="{_FONT}font-size:14px;color:#8b9097;margin:2px 0 14px;">{html.escape(text)}</div>'


def _reason(label: str, text: str) -> str:
    return f'<div style="{_FONT}font-size:14px;line-height:1.5;color:#4b5158;margin:4px 0;"><b>{label}:</b> {html.escape(text)}</div>'


def _counts(items: list[dict]) -> str:
    claims = sum(1 for i in items if i.get("type") == "claim")
    videos = sum(1 for i in items if i.get("type") != "claim" and i.get("kind") == "youtube")
    reads = len(items) - claims - videos
    return f"{len(items)} items ({reads} to read, {videos} videos, {claims} claims)"


def subject(items: list[dict]) -> str:
    """Build the email subject line."""
    return f"Your reposts digest: {_counts(items)}"


def _readmore_html(enrich: dict) -> str:
    pieces = [f'<a href="{html.escape(url)}" style="color:#0b5cad;text-decoration:none;">{html.escape(label)}</a>'
              for label, url in reference_links(enrich.get("references"))]
    rm = read_more_url(enrich.get("read_more", ""))
    if rm:
        pieces.append(f'<a href="{html.escape(rm)}" style="color:#0b5cad;text-decoration:none;">search this topic</a>')
    if not pieces:
        return ""
    return (f'<div style="{_FONT}font-size:14px;color:#6b7178;margin-top:16px;">'
            f'Read more: {" &middot; ".join(pieces)}</div>')


def _verdicts(enrich: dict) -> str:
    parts = [f'<div style="margin:4px 0 6px;">{_badge("Research", enrich.get("research_verdict"))}'
             f'{_badge("General", enrich.get("general_verdict"))}</div>']
    for label, key in (("Research", "research_reason"), ("General", "general_reason")):
        if enrich.get(key):
            parts.append(_reason(label, enrich[key]))
    return "".join(parts)


def _render_item_html(item: dict) -> str:
    enrich = item.get("enrichment") or {}
    meta = item.get("meta") or {}
    url = html.escape(item.get("final_url") or item.get("source_url") or "")
    title = html.escape(item.get("title") or item.get("final_url") or "Link")
    date = html.escape((item.get("date") or "")[:10])
    date_span = f'<span style="{_FONT}font-size:13px;color:#9aa0a6;margin-left:10px;">{date}</span>' if date else ""
    parts = ['<div style="border-top:1px solid #e9ecef;padding:28px 0;">']

    if item.get("type") == "claim":
        headline = html.escape(enrich.get("headline") or (item.get("repost_text") or "")[:90] or "Claim")
        parts.append(_kind_badge("claim", "Claim") + date_span)
        parts.append(_title("", headline))
        if item.get("author"):
            parts.append(_meta(f"@{item['author']}"))
        parts.append(_verdicts(enrich))
        if item.get("repost_text"):
            parts.append(f'<div style="{_FONT}font-size:17px;font-style:italic;color:#2b2f36;'
                         f'margin:12px 0;line-height:1.55;">&ldquo;{html.escape(item["repost_text"])}&rdquo;</div>')
        if enrich.get("context"):
            body = _CODE_PRE.sub("", md.markdown(_strip_code(enrich["context"]), extensions=["extra"]))
            parts.append(f'<div style="{_FONT}font-size:17px;line-height:1.65;color:#262a30;margin:10px 0;">{body}</div>')
        if url:
            parts.append(f'<div style="{_FONT}font-size:14px;color:#4b5158;margin:6px 0;">Linked: '
                         f'<a href="{url}" style="color:#0b5cad;text-decoration:none;">{title}</a></div>')
        parts.append(_readmore_html(enrich))

    elif item.get("kind") == "youtube":
        parts.append(_kind_badge("video", "Video") + date_span)
        parts.append(_title(url, title))
        bits = [b for b in (meta.get("channel"), meta.get("duration_human")) if b]
        parts.append(_meta(" | ".join(bits)))
        parts.append(_verdicts(enrich))
        if enrich.get("summary"):
            lis = "".join(f'<li style="margin:6px 0;">{html.escape(str(b))}</li>' for b in enrich["summary"])
            parts.append(f'<ul style="{_FONT}font-size:17px;line-height:1.6;color:#262a30;margin:10px 0;padding-left:22px;">{lis}</ul>')
        if enrich.get("time_note"):
            parts.append(f'<div style="{_FONT}font-size:13px;font-weight:700;color:#9a6a00;margin:6px 0;">{html.escape(enrich["time_note"])}</div>')
        parts.append(_readmore_html(enrich))

    elif item.get("kind") == "article":
        is_pdf = bool(meta.get("pdf"))
        parts.append(_kind_badge("pdf" if is_pdf else "article", "PDF" if is_pdf else "Article") + date_span)
        parts.append(_title(url, title))
        bits = [meta.get("sitename")]
        if is_pdf and meta.get("pages"):
            bits.append(f'{meta["pages"]} pages')
        bits.append(f'{item.get("reading_minutes", 0)} min read')
        parts.append(_meta(" | ".join(b for b in bits if b)))
        parts.append(_verdicts(enrich))
        if enrich.get("gist"):
            parts.append(f'<div style="{_FONT}font-size:17px;font-style:italic;color:#2b2f36;margin:10px 0;line-height:1.55;">{html.escape(enrich["gist"])}</div>')
        parts.append(_readmore_html(enrich))
        if item.get("text"):
            if meta.get("truncated"):
                parts.append(f'<div style="{_FONT}font-size:13px;font-weight:700;color:#9a6a00;margin:10px 0;">'
                             f'Showing the first part of a {meta.get("pages", "?")}-page PDF. '
                             f'Full document: <a href="{url}" style="color:#0b5cad;">{url}</a></div>')
            body = _CODE_PRE.sub("", md.markdown(_strip_code(item["text"]), extensions=["extra", "sane_lists"]))
            parts.append(f'<div style="{_FONT}font-size:17px;line-height:1.75;color:#1c1f24;margin-top:16px;'
                         f'padding-top:16px;border-top:1px dashed #e2e6ea;">{body}</div>')

    else:  # fallback
        parts.append(_kind_badge("", item.get("kind", "link")))
        parts.append(_title(url, title))
        if item.get("error"):
            parts.append(f'<div style="{_FONT}font-size:14px;color:#b00;">{html.escape(item["error"])}</div>')

    parts.append("</div>")
    return "".join(parts)


def render_html(items: list[dict]) -> str:
    """Render the digest as a wide, responsive HTML email."""
    header = (f'<h1 style="{_FONT}font-size:27px;line-height:1.25;margin:0 0 6px;color:#11151a;">Your reposts digest</h1>'
              f'<div style="{_FONT}font-size:14px;color:#6b7178;margin:0 0 2px;">{_counts(items)}.</div>'
              f'<div style="{_FONT}font-size:14px;color:#6b7178;">Two verdicts per item: research relevance and general value.</div>')
    body = "".join(_render_item_html(i) for i in items)
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="X-UA-Compatible" content="IE=edge">'
        '<style>@media screen and (max-width:640px){.wrap{padding:22px !important;}} '
        'body{margin:0;padding:0;}</style></head>'
        '<body style="margin:0;padding:0;background:#eceef1;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eceef1;">'
        '<tr><td align="center" style="padding:26px 12px;">'
        '<table role="presentation" width="640" cellpadding="0" cellspacing="0" '
        'style="max-width:640px;width:100%;background:#ffffff;border:1px solid #e6e8eb;border-radius:14px;">'
        '<tr><td class="wrap" style="padding:36px;">'
        f'{header}{body}'
        '</td></tr></table>'
        f'<div style="{_FONT}font-size:12px;color:#9aa0a6;padding:16px;">x-reader-digest</div>'
        '</td></tr></table></body></html>'
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
                lines.append(_strip_code(enrich["context"]))
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
            lines.append(_strip_code(item["text"]))
        lines.append("")
    return "\n".join(lines)
