"""Generate the static, filterable reading website from the archive.

Produces a self-contained docs/index.html (data embedded, so it works from a
local file and from GitHub Pages) plus docs/data.json for reuse. Items are
sorted newest first and filterable by verdict (recommended vs skipped), kind,
and free text.
"""

from __future__ import annotations

import json
import pathlib

from .links import read_more_url, reference_links
from .store import is_recommended


def _display_kind(item: dict) -> str:
    if item.get("type") == "claim":
        return "claim"
    if item.get("kind") == "youtube":
        return "video"
    if (item.get("meta") or {}).get("pdf"):
        return "pdf"
    return item.get("kind", "article")


def rank_score(item: dict) -> float:
    """Taste-match score for ranking; falls back when an item has no score."""
    score = (item.get("enrichment") or {}).get("score")
    if isinstance(score, (int, float)):
        return float(score)
    return 7.0 if is_recommended(item) else 3.0


def build_site_data(items: list[dict]) -> list[dict]:
    """Project archived items into the lightweight shape the page renders."""
    rows: list[dict] = []
    for item in items:
        enrich = item.get("enrichment") or {}
        meta = item.get("meta") or {}
        is_claim = item.get("type") == "claim"
        title = (enrich.get("headline") or item.get("repost_text", "")) if is_claim else item.get("title")
        links = [list(pair) for pair in reference_links(enrich.get("references"))]
        rm = read_more_url(enrich.get("read_more", ""))
        if rm:
            links.append(["search this topic", rm])
        rows.append(
            {
                "id": str(item.get("id") or item.get("final_url", "")),
                "date": item.get("date", ""),
                "kind": _display_kind(item),
                "title": title or item.get("final_url", "Link"),
                "url": item.get("final_url") or item.get("source_url", ""),
                "source": meta.get("sitename") or meta.get("channel") or "",
                "author": item.get("author", ""),
                "repost_text": item.get("repost_text", "") if is_claim else "",
                "context": enrich.get("context", "") if is_claim else "",
                "reading_minutes": item.get("reading_minutes", 0),
                "gist": enrich.get("gist", ""),
                "summary": enrich.get("summary", []),
                "research_verdict": (enrich.get("research_verdict") or "").upper(),
                "research_reason": enrich.get("research_reason", ""),
                "general_verdict": (enrich.get("general_verdict") or "").upper(),
                "general_reason": enrich.get("general_reason", ""),
                "time_note": enrich.get("time_note", ""),
                "links": links,
                "score": round(rank_score(item), 1),
                "recommended": is_recommended(item),
            }
        )
    rows.sort(key=lambda r: (r["score"], r["date"]), reverse=True)  # ranked feed
    return rows


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>My reposts, sorted</title>
<style>
:root{color-scheme:light dark;}
*{box-sizing:border-box;}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
margin:0;background:#fafafa;color:#1a1a1a;line-height:1.5;}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #e6e6e6;padding:14px 18px;z-index:5;}
h1{margin:0 0 10px;font-size:18px;}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;}
.controls button{border:1px solid #ccc;background:#fff;border-radius:18px;padding:6px 12px;font-size:13px;cursor:pointer;}
.controls button.on{background:#0a4d8c;color:#fff;border-color:#0a4d8c;}
.controls input{flex:1;min-width:160px;padding:7px 10px;border:1px solid #ccc;border-radius:8px;font-size:14px;}
.count{color:#777;font-size:12px;margin-left:auto;}
main{max-width:760px;margin:0 auto;padding:16px 18px 60px;}
.card{background:#fff;border:1px solid #e6e6e6;border-radius:10px;padding:16px;margin-bottom:14px;}
.row{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;}
.kind{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#fff;background:#888;border-radius:4px;padding:2px 6px;}
.kind.video{background:#b1442c;}.kind.pdf{background:#7a5a1d;}.kind.article{background:#3a6;}.kind.claim{background:#5b3a8a;}
.date{color:#999;font-size:12px;}
.title{font-size:16px;font-weight:600;margin:6px 0;}
.title a{color:#0a4d8c;text-decoration:none;}
.meta{color:#888;font-size:12px;margin-bottom:8px;}
.badges{margin:6px 0;}
.badge{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:5px;margin-right:6px;}
.go{background:#e6f4ea;color:#1d7a3a;}.no{background:#f0f0f0;color:#888;}
.gist{font-style:italic;color:#333;margin:6px 0;}
.ctx{color:#2a2a2a;font-size:14px;margin:8px 0;line-height:1.5;}
.rl{margin:8px 0 0;font-size:12px;color:#888;}.rl a{color:#0a4d8c;text-decoration:none;}
.reason{color:#555;font-size:13px;margin:2px 0;}
ul{margin:6px 0;padding-left:18px;}li{margin:3px 0;font-size:14px;}
.time{color:#9a6a00;font-size:12px;font-weight:600;}
.empty{color:#999;text-align:center;padding:40px;}
</style>
</head>
<body>
<header>
  <h1>My reposts, sorted <span id="updated" class="date"></span></h1>
  <div class="controls">
    <button data-f="recommended" class="on">Recommended</button>
    <button data-f="all">All</button>
    <button data-f="skipped">Skipped</button>
    <button data-k="all" class="on kindbtn">Any</button>
    <button data-k="claim" class="kindbtn">Claims</button>
    <button data-k="article" class="kindbtn">Articles</button>
    <button data-k="video" class="kindbtn">Videos</button>
    <button data-k="pdf" class="kindbtn">PDFs</button>
    <input id="q" placeholder="search title, source, text">
    <span id="count" class="count"></span>
  </div>
</header>
<main id="list"></main>
<script>
const DATA = __DATA__;
const state = {f:"recommended", k:"all", q:""};
const esc = s => (s||"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function badge(label, v){const go=(v==="READ"||v==="WATCH");return `<span class="badge ${go?"go":"no"}">${label}: ${esc(v||"?")}</span>`;}
function match(it){
  if(state.f==="recommended" && !it.recommended) return false;
  if(state.f==="skipped" && it.recommended) return false;
  if(state.k!=="all" && it.kind!==state.k) return false;
  if(state.q){const hay=(it.title+" "+it.source+" "+it.gist+" "+(it.summary||[]).join(" ")+" "+(it.context||"")+" "+(it.repost_text||"")).toLowerCase();
    if(!hay.includes(state.q)) return false;}
  return true;
}
function card(it){
  const isClaim=it.kind==="claim";
  const sum=(it.summary&&it.summary.length)?`<ul>${it.summary.map(b=>`<li>${esc(b)}</li>`).join("")}</ul>`:"";
  const gist=(!isClaim&&it.gist)?`<div class="gist">${esc(it.gist)}</div>`:"";
  const quote=(isClaim&&it.repost_text)?`<div class="gist">&ldquo;${esc(it.repost_text)}&rdquo;</div>`:"";
  const ctx=(isClaim&&it.context)?`<div class="ctx">${esc(it.context)}</div>`:"";
  const rr=it.research_reason?`<div class="reason"><b>Research:</b> ${esc(it.research_reason)}</div>`:"";
  const gr=it.general_reason?`<div class="reason"><b>General:</b> ${esc(it.general_reason)}</div>`:"";
  const tn=it.time_note?`<div class="time">${esc(it.time_note)}</div>`:"";
  const mins=it.reading_minutes?`${it.reading_minutes} min`:"";
  const meta=isClaim?(it.author?("@"+esc(it.author)):""):[esc(it.source),mins].filter(Boolean).join(" &middot; ");
  const titleHtml=it.url?`<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a>`:esc(it.title);
  const rl=(it.links&&it.links.length)?`<div class="rl">Read more: ${it.links.map(l=>`<a href="${esc(l[1])}" target="_blank" rel="noopener">${esc(l[0])}</a>`).join(" &middot; ")}</div>`:"";
  return `<div class="card"><div class="row"><span class="kind ${it.kind}">${it.kind}</span>
    <span class="date">${esc((it.date||"").slice(0,10))}</span></div>
    <div class="title">${titleHtml}</div>
    <div class="meta">${meta}</div>
    <div class="badges">${badge("Research",it.research_verdict)}${badge("General",it.general_verdict)}</div>
    ${quote}${gist}${ctx}${sum}${rr}${gr}${tn}${rl}</div>`;
}
function render(){
  const rows=DATA.filter(match);
  document.getElementById("list").innerHTML = rows.length
    ? rows.map(card).join("") : '<div class="empty">Nothing here. Try All, or clear the search.</div>';
  document.getElementById("count").textContent = rows.length+" of "+DATA.length;
}
document.querySelectorAll("[data-f]").forEach(b=>b.onclick=()=>{
  state.f=b.dataset.f; document.querySelectorAll("[data-f]").forEach(x=>x.classList.toggle("on",x===b)); render();});
document.querySelectorAll("[data-k]").forEach(b=>b.onclick=()=>{
  state.k=b.dataset.k; document.querySelectorAll("[data-k]").forEach(x=>x.classList.toggle("on",x===b)); render();});
document.getElementById("q").oninput=e=>{state.q=e.target.value.toLowerCase().trim(); render();};
document.getElementById("updated").textContent = "(" + DATA.length + " items)";
render();
</script>
</body>
</html>
"""


def generate(items: list[dict], docs_dir: pathlib.Path) -> int:
    """Write index.html (data embedded) and data.json into docs_dir.

    Returns
    -------
    int
        Number of items written to the site.
    """
    rows = build_site_data(items)
    docs_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, ensure_ascii=False)
    (docs_dir / "data.json").write_text(payload, encoding="utf-8")
    (docs_dir / "index.html").write_text(_PAGE.replace("__DATA__", payload), encoding="utf-8")
    return len(rows)
