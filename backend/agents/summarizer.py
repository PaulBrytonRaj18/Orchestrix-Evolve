"""Summarization Agent.

Per-paper summaries are produced by the LLM in JSON mode and normalised to the
columns the ``summaries`` table stores. Each result carries the ``paper_id`` of its
input so it can be persisted and joined (previously summaries had no id and were
silently dropped). Without an LLM key an extractive fallback is used, so the UI
always has something sensible to show.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from llm import get_llm

logger = logging.getLogger(__name__)

_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_ABSTRACT_CHARS = 1800

_SINGLE_SYSTEM = (
    "You are a precise research assistant. Summarise the paper using only the given "
    "title and abstract. Respond with a single JSON object and nothing else."
)
_SINGLE_SCHEMA = """{
  "abstract_compression": "one sentence capturing the core claim",
  "key_points": ["contribution 1", "contribution 2"],
  "methodology": "how the work was done",
  "limitations": "stated or evident limitations ('' if none are evident)",
  "strengths": "main strengths",
  "novelty_level": "low|medium|high",
  "key_takeaway": "one sentence for a busy researcher",
  "confidence_score": 0.0
}"""

_MULTI_SYSTEM = (
    "You are a research synthesis assistant. Compare the papers using only the given "
    "titles and abstracts. Respond with a single JSON object and nothing else."
)
_MULTI_SCHEMA = """{
  "common_themes": ["theme"],
  "key_combined_insights": ["insight"],
  "differences": ["difference"],
  "gaps": ["open question"],
  "unified_summary": "a cohesive 1-2 paragraph synthesis citing papers as [n]",
  "confidence_score": 0.0
}"""


def _sentences(text: str | None) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(" ".join((text or "").split())) if s.strip()]


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"• {str(v).strip()}" for v in value if str(v).strip())
    return str(value or "").strip()


def _input_confidence(paper: dict[str, Any]) -> float:
    abstract = paper.get("abstract") or ""
    if len(abstract) > 400:
        return 0.8
    if abstract:
        return 0.6
    return 0.3


def extractive_summary(paper: dict[str, Any]) -> dict[str, Any]:
    """Deterministic, offline summary from the abstract's own sentences."""
    sents = _sentences(paper.get("abstract"))
    lim = next(
        (s for s in sents if re.search(r"\b(limit|however|future work|challenge)", s, re.I)), ""
    )
    method = next(
        (
            s
            for s in sents
            if re.search(r"\b(we propose|we present|we introduce|using|based on)", s, re.I)
        ),
        "",
    )
    return {
        "paper_id": paper.get("id"),
        "title": paper.get("title", ""),
        "abstract_compression": sents[0] if sents else (paper.get("title") or ""),
        "key_contributions": _as_text(sents[1:3]),
        "methodology": method,
        "limitations": lim,
        "strengths": "",
        "novelty_level": "",
        "key_takeaway": sents[-1] if sents else "",
        "confidence_score": round(_input_confidence(paper) * 0.6, 2),
        "generated_by": "extractive",
    }


def _normalise(paper: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    try:
        confidence = float(data.get("confidence_score") or _input_confidence(paper))
    except (TypeError, ValueError):
        confidence = _input_confidence(paper)
    return {
        "paper_id": paper.get("id"),
        "title": paper.get("title", ""),
        "abstract_compression": _as_text(data.get("abstract_compression")),
        "key_contributions": _as_text(data.get("key_points") or data.get("key_contributions")),
        "methodology": _as_text(data.get("methodology") or data.get("explanation_approach")),
        "limitations": _as_text(data.get("limitations")),
        "strengths": _as_text(data.get("strengths")),
        "novelty_level": _as_text(data.get("novelty_level")),
        "key_takeaway": _as_text(data.get("key_takeaway")),
        "confidence_score": max(0.0, min(confidence, 1.0)),
        "generated_by": "llm",
    }


async def summarize_paper(paper: dict[str, Any]) -> dict[str, Any]:
    if not paper.get("abstract"):
        return extractive_summary(paper)
    prompt = (
        f"Title: {paper.get('title', 'N/A')}\n"
        f"Abstract: {(paper.get('abstract') or '')[:_ABSTRACT_CHARS]}\n\n"
        f"Return JSON with exactly these keys:\n{_SINGLE_SCHEMA}"
    )
    data = await get_llm().chat_json(_SINGLE_SYSTEM, prompt, max_tokens=700)
    return _normalise(paper, data) if data else extractive_summary(paper)


async def summarize_all_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarise papers concurrently (bounded by the shared LLM limiter), preserving order."""
    if not papers:
        return []
    return list(await asyncio.gather(*(summarize_paper(p) for p in papers)))


async def synthesize_papers(papers: list[dict[str, Any]]) -> dict[str, Any]:
    """Cross-paper synthesis. Always returns ``{"synthesis": str, ...structured fields}``."""
    if not papers:
        return {"synthesis": "No papers provided.", "generated_by": "none"}
    docs = "\n\n".join(
        f"[{i}] {p.get('title', 'Untitled')} ({p.get('year') or 'n.d.'}): "
        f"{(p.get('abstract') or '')[:700]}"
        for i, p in enumerate(papers, 1)
    )
    data = await get_llm().chat_json(
        _MULTI_SYSTEM,
        f"{docs}\n\nReturn JSON with exactly these keys:\n{_MULTI_SCHEMA}",
        max_tokens=1200,
    )
    if data and data.get("unified_summary"):
        return {**data, "synthesis": str(data["unified_summary"]).strip(), "generated_by": "llm"}

    lines = [
        f"[{i}] {p.get('title', 'Untitled')} ({p.get('year') or 'n.d.'}): "
        f"{(_sentences(p.get('abstract')) or ['No abstract available.'])[0]}"
        for i, p in enumerate(papers, 1)
    ]
    return {
        "synthesis": "Key claims of the selected papers (LLM unavailable, extractive view):\n"
        + "\n".join(lines),
        "generated_by": "extractive",
    }
