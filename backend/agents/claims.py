"""Claim extraction and evidence-backed contradiction detection between papers.

1. **Extract** up to three result claims per paper from its abstract:
   ``{text, subject, outcome, direction, dataset, metric, value, evidence}``, where
   ``evidence`` is a verbatim sentence. The LLM does this in batches; without it a
   sentence-level heuristic keeps result sentences and reads their direction.
2. **Pair** claims from *different* papers that talk about the same thing
   (cosine similarity of claim embeddings, keyword overlap as fallback).
3. **Judge** each candidate pair: contradiction / agreement / unrelated with a
   confidence and a one-sentence reason (LLM, batched). The heuristic only flags
   pairs whose directions are opposite.

Only contradictions become conflicts, each citing both papers and both quotes.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import numpy as np

from constants import STOPWORDS
from llm import get_llm

logger = logging.getLogger(__name__)

DIRECTIONS = ("increase", "decrease", "no_effect", "positive", "negative", "neutral")
OPPOSITE = {
    "increase": {"decrease", "no_effect"},
    "decrease": {"increase", "no_effect"},
    "no_effect": {"increase", "decrease", "positive", "negative"},
    "positive": {"negative", "no_effect"},
    "negative": {"positive", "no_effect"},
}
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_RESULT_CUES = re.compile(
    r"\b(we (show|find|found|demonstrate|observe)|results? (show|indicate|suggest)|outperform|"
    r"improv|increas|reduc|decreas|achiev|significant|no (significant|evidence)|fail|"
    r"does not|did not|higher|lower|better|worse|effective|ineffective)",
    re.I,
)
_NO_EFFECT = re.compile(
    r"\b(no (significant )?(effect|difference|improvement|benefit|evidence)|did not|does not|"
    r"do not|fail(s|ed)? to|not (significantly )?(improve|increase|reduce|affect)|comparable)",
    re.I,
)
_UP = re.compile(r"\b(improv|increas|outperform|enhanc|boost|higher|better|gain|effective)", re.I)
_DOWN = re.compile(
    r"\b(reduc|decreas|lower|worse|degrad|declin|harm|ineffective|drop(s|ped)?\b|loses?\b|loss of)",
    re.I,
)
_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*(%|percent)?")
_METRICS = ("accuracy", "f1", "auc", "auroc", "bleu", "rmse", "mae", "precision", "recall",
            "mortality", "survival", "error", "latency", "throughput", "perplexity", "ndcg")  # fmt: skip


def _content_words(text: str) -> set[str]:
    return {
        w
        for w in re.findall(r"[a-z][a-z0-9\-]+", (text or "").lower())
        if w not in STOPWORDS and len(w) > 2
    }


# ─── extraction ──────────────────────────────────────────────────────────────


def claim_direction(sentence: str) -> str:
    """increase / decrease / no_effect / neutral from cue words."""
    if _NO_EFFECT.search(sentence):
        return "no_effect"
    up, down = bool(_UP.search(sentence)), bool(_DOWN.search(sentence))
    if up and not down:
        return "increase"
    if down and not up:
        return "decrease"
    return "neutral"


def heuristic_claims(paper: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    """Result sentences from the abstract, with a direction read from cue words."""
    sentences = _SENTENCE.split(" ".join((paper.get("abstract") or "").split()))
    claims = []
    for sentence in sentences:
        if len(sentence) < 40 or not _RESULT_CUES.search(sentence):
            continue
        direction = claim_direction(sentence)
        lower = sentence.lower()
        metric = next((m for m in _METRICS if re.search(rf"\b{m}\b", lower)), None)
        number = _NUMBER.search(sentence) if metric else None
        claims.append(
            {
                "text": sentence[:400],
                "subject": None,
                "outcome": metric,
                "direction": direction,
                "dataset": None,
                "metric": metric,
                "value": float(number.group(1)) if number else None,
                "evidence": sentence[:600],
                "generated_by": "heuristic",
            }
        )
        if len(claims) == limit:
            break
    return claims


_EXTRACT_SYSTEM = (
    "You extract the main empirical result claims from research abstracts. Use only the "
    "abstract text. Respond with a single JSON object and nothing else."
)
_CLAIM_SCHEMA = (
    '{"text": "the claim in one sentence", "subject": "method/intervention studied", '
    '"outcome": "what was measured or affected", "direction": "increase|decrease|no_effect|'
    'positive|negative|neutral", "dataset": "dataset or population or null", "metric": '
    '"metric or null", "value": number or null, "evidence": "verbatim sentence from the abstract"}'
)


def _clean_claim(item: dict[str, Any], abstract: str) -> dict[str, Any] | None:
    text = str(item.get("text") or "").strip()
    if not text:
        return None
    direction = str(item.get("direction") or "neutral").lower().strip()
    evidence = str(item.get("evidence") or "").strip()
    if evidence and evidence.lower() not in abstract.lower():
        evidence = ""  # never show a "quote" the paper does not contain
    try:
        value = float(item["value"]) if item.get("value") not in (None, "") else None
    except (TypeError, ValueError):
        value = None
    return {
        "text": text[:400],
        "subject": (str(item.get("subject")).strip()[:200] or None)
        if item.get("subject")
        else None,
        "outcome": (str(item.get("outcome")).strip()[:200] or None)
        if item.get("outcome")
        else None,
        "direction": direction if direction in DIRECTIONS else "neutral",
        "dataset": (str(item.get("dataset")).strip()[:200] or None)
        if item.get("dataset")
        else None,
        "metric": (str(item.get("metric")).strip()[:100] or None) if item.get("metric") else None,
        "value": value,
        "evidence": evidence[:600] or None,
        "generated_by": "llm",
    }


async def _extract_batch(batch: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    docs = "\n\n".join(
        f"[{i}] Title: {p.get('title', '')}\nAbstract: {(p.get('abstract') or '')[:1800]}"
        for i, p in enumerate(batch, 1)
    )
    data = await get_llm().chat_json(
        _EXTRACT_SYSTEM,
        f'{docs}\n\nReturn {{"papers": [{{"index": n, "claims": [up to 3 objects like '
        f"{_CLAIM_SCHEMA}]}}]}} with one entry per paper.",
        max_tokens=min(700 * len(batch), 3500),
        temperature=0.1,
    )
    found: dict[int, list[dict[str, Any]]] = {}
    for entry in (data or {}).get("papers") or []:
        try:
            idx = int(entry.get("index"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 1 <= idx <= len(batch):
            abstract = batch[idx - 1].get("abstract") or ""
            cleaned = [
                _clean_claim(c, abstract)
                for c in (entry.get("claims") or [])[:3]
                if isinstance(c, dict)
            ]
            found[idx - 1] = [c for c in cleaned if c]
    # Papers the model skipped still get heuristic claims.
    return [found.get(i) or heuristic_claims(p) for i, p in enumerate(batch)]


async def extract_claims(
    papers: list[dict[str, Any]], batch_size: int = 4
) -> dict[str, list[dict]]:
    """``{paper id: [claim, ...]}`` for papers that have an abstract."""
    from services.works import stored_claims

    with_abstract = [p for p in papers if p.get("abstract") and p.get("id")]
    if not with_abstract:
        return {}
    reused = await asyncio.to_thread(stored_claims, with_abstract)
    # Re-extract only when nothing is stored, or when the LLM can now beat a heuristic set.
    llm_on = get_llm().enabled
    todo = [
        p
        for p in with_abstract
        if p["id"] not in reused
        or (llm_on and all(c.get("generated_by") != "llm" for c in reused[p["id"]]))
    ]
    fresh: dict[str, list[dict[str, Any]]] = {}
    if todo and not llm_on:
        fresh = {p["id"]: heuristic_claims(p) for p in todo}
    elif todo:
        batches = [todo[i : i + batch_size] for i in range(0, len(todo), batch_size)]
        results = await asyncio.gather(*(_extract_batch(b) for b in batches))
        fresh = {
            p["id"]: claims
            for b, r in zip(batches, results, strict=True)
            for p, claims in zip(b, r, strict=True)
        }
    return {p["id"]: fresh.get(p["id"]) or reused.get(p["id"], []) for p in with_abstract}


# ─── pairing ─────────────────────────────────────────────────────────────────


def _claim_text(c: dict[str, Any]) -> str:
    parts = [c.get("subject"), c.get("outcome"), c.get("dataset"), c.get("text")]
    return " ".join(p for p in parts if p)


def candidate_pairs(
    claims: dict[str, list[dict[str, Any]]], max_pairs: int = 30, threshold: float = 0.72
) -> list[tuple[dict, dict, float]]:
    """Claims from different papers about the same thing, most similar first."""
    flat = [(pid, c) for pid, cs in claims.items() for c in cs]
    if len(flat) < 2:
        return []
    from services.embeddings import get_embedder

    embedder = get_embedder()
    sims = None
    if embedder is not None and embedder.available:
        try:
            vectors = embedder.embed_documents([_claim_text(c) for _, c in flat])
            sims = vectors @ vectors.T
        except Exception:
            logger.exception("Claim embedding failed; using keyword overlap")
    if sims is None:
        words = [_content_words(_claim_text(c)) for _, c in flat]
        sims = np.zeros((len(flat), len(flat)), dtype=np.float32)
        for i in range(len(flat)):
            for j in range(i + 1, len(flat)):
                union = words[i] | words[j]
                sims[i, j] = sims[j, i] = len(words[i] & words[j]) / len(union) if union else 0.0
        threshold = min(threshold, 0.3)  # Jaccard runs on a much lower scale than cosine
    pairs = []
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            if flat[i][0] != flat[j][0] and sims[i, j] >= threshold:
                a = dict(flat[i][1], paper_id=flat[i][0])
                b = dict(flat[j][1], paper_id=flat[j][0])
                pairs.append((a, b, float(sims[i, j])))
    pairs.sort(key=lambda t: -t[2])
    return pairs[:max_pairs]


# ─── judging ─────────────────────────────────────────────────────────────────


def heuristic_judgement(a: dict[str, Any], b: dict[str, Any], similarity: float) -> dict[str, Any]:
    if b.get("direction") in OPPOSITE.get(a.get("direction") or "", set()):
        return {
            "relation": "contradiction",
            "confidence": round(min(0.6, 0.3 + similarity / 2), 2),
            "explanation": f"One paper reports {a['direction'].replace('_', ' ')} where the other "
            f"reports {b['direction'].replace('_', ' ')} for a closely related claim.",
            "detected_by": "heuristic",
        }
    return {
        "relation": "unrelated",
        "confidence": 0.0,
        "explanation": "",
        "detected_by": "heuristic",
    }


_JUDGE_SYSTEM = (
    "You are a careful scientific reviewer. For each pair of claims from two different "
    "papers decide whether they CONTRADICT each other (they cannot both be true for the "
    "same setting), AGREE, or are UNRELATED (different settings, populations, metrics or "
    "questions — different numbers from different methods are NOT a contradiction). "
    "Respond with a single JSON object and nothing else."
)


async def _judge_batch(batch: list[tuple[dict, dict, float]]) -> list[dict[str, Any]]:
    listing = "\n\n".join(
        f"[{i}] A: {a['text']}"
        + (f" (evidence: {a['evidence']})" if a.get("evidence") else "")
        + f"\n    B: {b['text']}"
        + (f" (evidence: {b['evidence']})" if b.get("evidence") else "")
        for i, (a, b, _) in enumerate(batch, 1)
    )
    data = await get_llm().chat_json(
        _JUDGE_SYSTEM,
        f'{listing}\n\nReturn {{"pairs": [{{"index": n, "relation": '
        f'"contradiction|agreement|unrelated", "confidence": 0.0-1.0, "explanation": '
        f'"one sentence"}}]}} covering every pair.',
        max_tokens=120 * len(batch) + 100,
        temperature=0.0,
    )
    verdicts: dict[int, dict[str, Any]] = {}
    for item in (data or {}).get("pairs") or []:
        try:
            idx = int(item["index"])
            relation = str(item["relation"]).lower().strip()
            confidence = max(0.0, min(float(item.get("confidence", 0.5)), 1.0))
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= idx <= len(batch) and relation in ("contradiction", "agreement", "unrelated"):
            verdicts[idx - 1] = {
                "relation": relation,
                "confidence": round(confidence, 2),
                "explanation": str(item.get("explanation") or "")[:500],
                "detected_by": "llm",
            }
    return [verdicts.get(i) or heuristic_judgement(a, b, s) for i, (a, b, s) in enumerate(batch)]


async def judge_pairs(pairs: list[tuple[dict, dict, float]], batch_size: int = 8) -> list[dict]:
    if not pairs:
        return []
    if not get_llm().enabled:
        return [heuristic_judgement(a, b, s) for a, b, s in pairs]
    batches = [pairs[i : i + batch_size] for i in range(0, len(pairs), batch_size)]
    results = await asyncio.gather(*(_judge_batch(b) for b in batches))
    return [v for r in results for v in r]


def _severity(confidence: float) -> str:
    return "high" if confidence >= 0.8 else "medium" if confidence >= 0.6 else "low"


async def detect_conflicts(
    papers: list[dict[str, Any]], claims: dict[str, list[dict[str, Any]]] | None = None
) -> dict[str, Any]:
    """Contradictions between papers' claims → conflict dicts ready for persistence."""
    if claims is None:
        claims = await extract_claims(papers)
    titles = {p["id"]: p.get("title", "") for p in papers if p.get("id")}
    pairs = candidate_pairs(claims)
    verdicts = await judge_pairs(pairs)
    conflicts, seen = [], set()
    for (a, b, sim), v in zip(pairs, verdicts, strict=True):
        if v["relation"] != "contradiction":
            continue
        key = tuple(sorted((a["paper_id"], b["paper_id"])))
        if key in seen:  # one conflict per paper pair: the strongest
            continue
        seen.add(key)
        topic = a.get("outcome") or b.get("outcome") or "the same question"
        conflicts.append(
            {
                "conflict_type": "claim_contradiction",
                "severity": _severity(v["confidence"]),
                "title": f"Contradicting findings on {topic}"[:500],
                "description": v["explanation"],
                "analysis_insight": f"{titles.get(a['paper_id'], '')}: {a['text']}",
                "summarization_insight": f"{titles.get(b['paper_id'], '')}: {b['text']}",
                "paper_a_id": a["paper_id"],
                "paper_b_id": b["paper_id"],
                "evidence_a": a.get("evidence"),
                "evidence_b": b.get("evidence"),
                "confidence": v["confidence"],
                "similarity": round(sim, 3),
                "detected_by": v["detected_by"],
            }
        )
    conflicts.sort(key=lambda c: -c["confidence"])
    counts = {s: sum(1 for c in conflicts if c["severity"] == s) for s in ("high", "medium", "low")}
    summary = (
        f"{len(conflicts)} contradicting claim pair(s) among {len(pairs)} closely related pairs "
        f"from {len(claims)} papers."
        if conflicts
        else f"No contradictions among {len(pairs)} closely related claim pairs."
    )
    return {
        "conflicts": conflicts,
        "summary": summary,
        "stats": {"total": len(conflicts), **counts, "pairs_checked": len(pairs)},
        "claims": claims,
    }
