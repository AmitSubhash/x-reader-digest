"""Summarize extracted items and assign verdicts using `claude -p` (sonnet).

This module shells out to the local Claude Code CLI in headless print mode, so
it relies on the existing subscription auth and needs no API key. For videos it
produces a short summary plus a watch verdict; for articles it produces two
"worth your time" labels while the full text is delivered separately.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict
from typing import Optional

from .extract import ExtractedItem

# The verdict is judged on two independent axes, per the user's request.
RESEARCH_PROFILE = (
    "Amit is an incoming PhD in neuroengineering, but his interests are broad. Treat ALL of the "
    "following as research-relevant (research_verdict READ/WATCH), not just his thesis topic: "
    "diffuse optical tomography (DOT), fNIRS, neonatal and medical brain imaging, Monte Carlo "
    "photon transport, and inverse problems; reinforcement learning (RL) of any flavor; machine "
    "learning and deep learning broadly (architectures, training, theory, evals); computational and "
    "medical imaging; agent engineering / agentic AI / LLM tooling, orchestration, and prompting "
    "(he builds a lot of this with Claude Max and enjoys it); and GPU kernel programming and low-level "
    "performance work (CUDA, Triton, kernels, GPU optimization), which he is actively curious about. "
    "ADVICE IS A TOP PRIORITY: any advice at all (research advice, research-craft, how-to-do-research, "
    "taste, career and job advice, PhD and mentorship advice, productivity, life and work wisdom) MUST be "
    "marked READ, ideally on both axes, because he wants to read all of it. Lean strongly toward READ "
    "whenever an item plausibly touches any of these."
)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def claude_p(prompt: str, model: str = "sonnet", timeout: float = 180.0) -> str:
    """Run a prompt through `claude -p` headless and return stdout text.

    Parameters
    ----------
    prompt : str
        The full prompt, passed on stdin to avoid argument-length limits.
    model : str
        Model alias to pass to `--model` (default "sonnet").
    timeout : float
        Hard timeout in seconds.

    Returns
    -------
    str
        The model's text response, stripped.

    Raises
    ------
    RuntimeError
        If the CLI exits non-zero or times out.
    """
    try:
        proc = subprocess.run(
            ["claude", "-p", "--model", model],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(f"claude -p timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed ({proc.returncode}): {proc.stderr.strip()[:400]}")
    return proc.stdout.strip()


def _parse_json(raw: str) -> dict:
    """Pull the first JSON object out of a model response."""
    match = _JSON_BLOCK.search(raw)
    if not match:
        raise ValueError(f"no JSON found in response: {raw[:200]}")
    return json.loads(match.group(0))


def _video_prompt(item: ExtractedItem) -> str:
    """Build the summarize-and-judge prompt for a video."""
    meta = item.meta
    body = item.text[:14000]
    transcript_note = (
        "Transcript follows." if meta.get("has_transcript") else
        "No transcript available; only the video description follows. Judge cautiously and say so."
    )
    return f"""You are triaging a YouTube video that Amit reposted on X, so he can decide whether to watch it.

{RESEARCH_PROFILE}

Video: {item.title}
Channel: {meta.get("channel", "")}
Length: {meta.get("duration_human", "unknown")}
{transcript_note}

CONTENT:
{body}

Return ONLY a JSON object, no prose, no code fences, with these keys:
- "summary": array of 3 to 5 short bullet strings capturing the actual substance (claims, findings, what you would learn), not vibes.
- "research_verdict": "WATCH" or "SKIP" judged purely on relevance to Amit's research above.
- "research_reason": one sentence, why.
- "general_verdict": "WATCH" or "SKIP" judged on general signal and learning value regardless of field.
- "general_reason": one sentence, why.
- "time_note": one short phrase weighing payoff against the runtime.
Do not use em dashes anywhere. Use commas or parentheses instead."""


def _article_prompt(item: ExtractedItem) -> str:
    """Build the judge prompt for an article (full text is delivered separately)."""
    body = item.text[:14000]
    return f"""You are triaging an article that Amit reposted on X. The full text is delivered to him separately, so do NOT summarize at length; just judge whether it is worth his time and give a one-line gist.

{RESEARCH_PROFILE}

Article: {item.title}
Source: {item.meta.get("sitename", "")}
Estimated reading time: {item.reading_minutes} min

CONTENT:
{body}

Return ONLY a JSON object, no prose, no code fences, with these keys:
- "gist": one sentence on what the article actually argues or reports.
- "research_verdict": "READ" or "SKIP" judged purely on relevance to Amit's research above.
- "research_reason": one sentence, why.
- "general_verdict": "READ" or "SKIP" judged on general signal and learning value regardless of field.
- "general_reason": one sentence, why.
Do not use em dashes anywhere. Use commas or parentheses instead."""


def summarize_item(item: ExtractedItem, model: str = "sonnet") -> dict:
    """Enrich one extracted item with a summary and two verdicts.

    Parameters
    ----------
    item : ExtractedItem
        A populated extraction result.
    model : str
        Model alias for `claude -p`.

    Returns
    -------
    dict
        The item as a dict with an added "enrichment" key (or "enrich_error").
    """
    out = asdict(item)
    if item.error or not item.text:
        out["enrichment"] = None
        out["enrich_error"] = item.error or "no content to summarize"
        return out

    prompt = _video_prompt(item) if item.kind == "youtube" else _article_prompt(item)
    try:
        out["enrichment"] = _parse_json(claude_p(prompt, model=model))
        out["enrich_error"] = None
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        out["enrichment"] = None
        out["enrich_error"] = str(exc)[:300]
    return out


def summarize_all(items: list[ExtractedItem], model: str = "sonnet") -> list[dict]:
    """Summarize a list of extracted items sequentially."""
    return [summarize_item(item, model=model) for item in items]


def _analyze_prompt(repost: dict, resource: Optional[ExtractedItem]) -> str:
    """Build the unified per-repost prompt (resource summary or claim context)."""
    author = repost.get("author", "")
    author_name = repost.get("author_name", "")
    repost_text = (repost.get("text") or "").strip()

    if resource is not None and resource.text:
        kind = "video" if resource.kind == "youtube" else resource.kind
        source = (resource.meta or {}).get("sitename") or (resource.meta or {}).get("channel") or ""
        resource_block = (
            f"It links to a {kind}: \"{resource.title}\" ({source}).\n"
            f"Content excerpt:\n{resource.text[:8000]}"
        )
    else:
        resource_block = "There is no readable external link; the substance is the tweet itself."

    return f"""You are triaging one X repost for Amit so his morning reading actually makes sense, not just a link dump.

{RESEARCH_PROFILE}

The repost (originally posted by @{author}, {author_name}):
\"\"\"{repost_text}\"\"\"

{resource_block}

Decide the TYPE:
- "resource": the repost is essentially sharing something to read or watch; the value is the linked content.
- "claim": the repost makes an assertion, opinion, recommendation, or references a person / paper / lab / idea, where Amit needs context to understand WHY it was said.

Return ONLY a JSON object, no prose, no code fences:
- "type": "resource" or "claim".
- "headline": one short line naming what this is.
- "context": for a CLAIM, 3 to 6 sentences that (a) restate the claim plainly, (b) identify and briefly explain any person, paper, lab, or concept referenced (who they are, what they did, and a couple of their key works if a researcher), and (c) explain why the claim was made or what background makes it make sense. For a resource, "".
- "gist": for a resource ARTICLE or PDF, one sentence on what it argues. Else "".
- "summary": for a resource VIDEO, an array of 3 to 5 short bullet strings. If it is a lecture or talk, be thorough and capture the main points actually taught (use the transcript). Else [].
- "research_verdict": "READ"/"WATCH" or "SKIP", judged on relevance to Amit's research above. Count research-craft, how-to-do-research, taste, and PhD advice as research-relevant.
- "research_reason": one sentence.
- "general_verdict": "READ"/"WATCH" or "SKIP", judged on general signal and learning value.
- "general_reason": one sentence.
- "time_note": for videos, payoff versus runtime; else "".
- "references": array (up to 4) of objects {{"name": str, "kind": "person"|"paper"|"lab"|"tool"|"concept"}} naming the people, papers, labs, tools, or concepts a curious reader should look up to understand this repost. [] if none.
- "read_more": a short, specific web-search query (5 to 10 words) to dig deeper into the core topic.
Never include code snippets, code blocks, shell commands, or config in any field; describe in prose instead.
Do not use em dashes anywhere. Use commas or parentheses instead."""


def analyze(repost: dict, resource: Optional[ExtractedItem], model: str = "sonnet") -> Optional[dict]:
    """Analyze one repost: summarize a resource or explain a claim.

    Parameters
    ----------
    repost : dict
        The repost with "text", "author", "author_name".
    resource : ExtractedItem, optional
        The extracted linked content, or None for a text-only claim.
    model : str
        Model alias for `claude -p`.

    Returns
    -------
    dict or None
        The validated enrichment, or None if the model call failed.
    """
    prompt = _analyze_prompt(repost, resource)  # build outside try so bugs surface
    try:
        return _parse_json(claude_p(prompt, model=model))
    except (RuntimeError, ValueError, json.JSONDecodeError):
        return None
