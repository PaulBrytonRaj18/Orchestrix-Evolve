import json
import os
import asyncio
import time
import logging
from dotenv import load_dotenv
from typing import List, Dict, Optional
from groq import AsyncGroq

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# ── Rate limiting configuration ──
# Free tier: ~10 req/min, Pro: ~60 req/min
# Use environment variable or fallback to conservative default
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "3"))
REQUEST_TIMEOUT = float(os.getenv("GROQ_TIMEOUT", "30.0"))

# Rate limit tracking
_rate_limit_state = {
    "last_request_time": 0.0,
    "request_count": 0,
    "window_start": 0.0,
    "requests_per_minute": int(os.getenv("GROQ_RATE_LIMIT_RPM", "10")),
}

_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# ─────────────────────────── UTILS ───────────────────────────


def _truncate(text: Optional[str], limit: int = 300) -> str:
    return (text or "")[:limit]


def _clean(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
    return text.strip()


def _safe_json(text: str) -> Optional[Dict]:
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except Exception:
                pass
        return None


def _confidence(paper: Dict) -> float:
    score = 0.0
    if paper.get("title"):
        score += 0.5
    if paper.get("abstract"):
        score += 1.0
    return round(score / 2, 2)


def _deduplicate(docs: List[Dict]) -> List[Dict]:
    seen, result = set(), []
    for d in docs:
        key = d.get("title", "").lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(d)
    return result


def _detect_conflicts(docs: List[Dict]) -> List[str]:
    years = {d.get("year") for d in docs if d.get("year")}
    return ["Different publication years detected"] if len(years) > 1 else []


_FALLBACK_SINGLE = {
    "derived_content": {"abstract_compression": "", "key_points": []},
    "inferred_content": {
        "explanation_approach": "",
        "strengths": "",
        "limitations": "",
        "novelty_level": "",
    },
    "key_takeaway": "Could not generate summary.",
    "confidence_score": 0.3,
}

_FALLBACK_MULTI = {
    "derived_content": {"common_themes": [], "key_combined_insights": []},
    "inferred_content": {"differences": ["Invalid JSON from model"], "gaps": []},
    "unified_summary": "Could not generate structured summary.",
    "confidence_score": 0.3,
}

# ─────────────────────────── CORE ────────────────────────────


async def _call_groq(prompt: str) -> str:
    """
    Rate-limited, fully async Groq call.
    The semaphore ensures we never exceed MAX_CONCURRENT_REQUESTS in-flight.
    Also enforces requests-per-minute limit.
    """
    global _rate_limit_state

    if len(prompt) > 12_000:
        prompt = prompt[:12_000]

    # Rate limit enforcement based on time window
    current_time = time.time()
    window_duration = 60.0  # 1 minute window

    # Reset window if expired
    if current_time - _rate_limit_state["window_start"] >= window_duration:
        _rate_limit_state["request_count"] = 0
        _rate_limit_state["window_start"] = current_time

    # Check if we've hit rate limit
    while (
        _rate_limit_state["request_count"] >= _rate_limit_state["requests_per_minute"]
    ):
        wait_time = window_duration - (current_time - _rate_limit_state["window_start"])
        if wait_time > 0:
            logger.warning(
                f"Rate limit reached ({_rate_limit_state['requests_per_minute']} req/min). Waiting {wait_time:.1f}s"
            )
            await asyncio.sleep(wait_time)
        current_time = time.time()
        if current_time - _rate_limit_state["window_start"] >= window_duration:
            _rate_limit_state["request_count"] = 0
            _rate_limit_state["window_start"] = current_time

    # Track request
    _rate_limit_state["request_count"] += 1
    _rate_limit_state["last_request_time"] = current_time

    async with _semaphore:
        client = AsyncGroq(api_key=GROQ_API_KEY)
        try:
            res = await asyncio.wait_for(
                client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "Return ONLY valid JSON. No explanation, no markdown.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.5,
                    max_tokens=1024,
                ),
                timeout=REQUEST_TIMEOUT,
            )
            return _clean(res.choices[0].message.content)
        except asyncio.TimeoutError:
            logger.error("Groq API request timed out")
            raise Exception("Groq API request timed out")
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise


# ─────────────────────────── SINGLE PAPER ────────────────────


def _build_single_prompt(paper: Dict) -> str:
    return f"""
Summarize this research paper.

Title: {paper.get("title", "N/A")}
Abstract: {_truncate(paper.get("abstract"))}

Return ONLY this JSON (no extra text):
{{
  "derived_content": {{
    "abstract_compression": "one-sentence compression",
    "key_points": ["point1", "point2"]
  }},
  "inferred_content": {{
    "explanation_approach": "...",
    "strengths": "...",
    "limitations": "...",
    "novelty_level": "low|medium|high"
  }},
  "key_takeaway": "...",
  "confidence_score": 0.0
}}
"""


async def _summarize_one(paper: Dict) -> Dict:
    """Summarize a single paper asynchronously."""
    try:
        raw = await _call_groq(_build_single_prompt(paper))
        data = _safe_json(raw)
        if not data:
            return {**_FALLBACK_SINGLE, "title": paper.get("title", "")}
        data.setdefault("confidence_score", _confidence(paper))
        data["title"] = paper.get("title", "")
        return data
    except Exception as e:
        return {**_FALLBACK_SINGLE, "error": str(e), "title": paper.get("title", "")}


# ─────────────────────────── BATCH PARALLEL ──────────────────


async def summarize_all_papers(
    papers: List[Dict], purpose: str = "general"
) -> List[Dict]:
    """
    🚀 Summarize ALL papers in parallel with a single gather call.
    Replaces the old one-by-one loop — latency = slowest single call, not sum of all.
    """
    if not papers:
        return []

    papers = _deduplicate(papers)

    # Fire all coroutines simultaneously, bounded by the semaphore
    results = await asyncio.gather(
        *[_summarize_one(p) for p in papers],
        return_exceptions=False,  # individual errors caught inside _summarize_one
    )
    return list(results)


# ─────────────────────────── MULTI-DOC COMPARE ───────────────


def _build_multi_prompt(docs: List[Dict], conflicts: List[str]) -> str:
    docs_text = "\n\n".join(
        f"[{i + 1}] {d.get('title', 'Untitled')} ({d.get('year', '?')}): "
        f"{_truncate(d.get('abstract'))}"
        for i, d in enumerate(docs)
    )
    return f"""
Compare the following research papers.

{docs_text}

Detected conflicts: {conflicts if conflicts else "None"}

Return ONLY this JSON (no extra text):
{{
  "derived_content": {{
    "common_themes": ["theme1"],
    "key_combined_insights": ["insight1"]
  }},
  "inferred_content": {{
    "differences": ["diff1"],
    "gaps": ["gap1"]
  }},
  "unified_summary": "...",
  "confidence_score": 0.0
}}
"""


async def summarize_documents(docs: List[Dict], purpose: str = "general") -> Dict:
    """
    Produce a unified comparative summary for a list of papers.
    Also runs individual summaries concurrently so the UI can show
    both per-paper and combined results without waiting twice.
    """
    if not docs:
        return {**_FALLBACK_MULTI, "error": "No documents provided"}

    docs = _deduplicate(docs)
    conflicts = _detect_conflicts(docs)

    # Run individual + combined summarisation concurrently
    individual_task = summarize_all_papers(docs, purpose)
    combined_task = _call_groq(_build_multi_prompt(docs, conflicts))

    individual_results, combined_raw = await asyncio.gather(
        individual_task, combined_task
    )

    combined = _safe_json(combined_raw) or {**_FALLBACK_MULTI}
    combined["individual_summaries"] = (
        individual_results  # bonus: per-paper details for UI
    )
    return combined


# ─────────────────────────── SYNTHESIS ───────────────────────


async def synthesize_papers(papers: List[Dict], purpose: str = "academic") -> str:
    """
    Entry point for the Discovery Agent → UI pipeline.
    Returns the unified summary string (fast path).
    Individual summaries are embedded in the payload for the UI layer.
    """
    if not papers:
        return "No papers provided."

    result = await summarize_documents(papers, purpose)
    return result.get("unified_summary", "Synthesis failed.")


# ─────────────────────────── FULL PIPELINE ───────────────────


async def run_full_pipeline(papers: List[Dict], purpose: str = "academic") -> Dict:
    """
    🏎️  One call to rule them all.
    Returns a structured payload the UI can render immediately:
    {
      "unified_summary":     str,
      "individual_summaries": [ {title, key_takeaway, confidence_score, ...} ],
      "derived_content":     { common_themes, key_combined_insights },
      "inferred_content":    { differences, gaps },
      "confidence_score":    float
    }
    """
    if not papers:
        return {**_FALLBACK_MULTI, "individual_summaries": []}

    return await summarize_documents(papers, purpose)
