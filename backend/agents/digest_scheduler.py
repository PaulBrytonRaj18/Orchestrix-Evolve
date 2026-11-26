"""Scheduled Digest Agent — finds papers published since a digest's last run.

Reuses the Discovery agent's source clients (with their date filters) instead of
maintaining a second, divergent copy of the Semantic Scholar / arXiv code.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta

from agents import discovery

_FREQUENCY_DELTAS: dict[str, timedelta | relativedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "biweekly": timedelta(weeks=2),
    "monthly": relativedelta(months=1),
}


def normalize_string(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def get_frequency_delta(frequency: str) -> timedelta | relativedelta:
    return _FREQUENCY_DELTAS.get(frequency, _FREQUENCY_DELTAS["weekly"])


def calculate_next_run(last_run: datetime, frequency: str) -> datetime:
    if last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=UTC)
    return last_run + get_frequency_delta(frequency)


async def run_digest(
    query: str,
    last_run_at: datetime | None = None,
    existing_external_ids: list[str] | set[str] | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    """Return papers published on/after the threshold that are not already known."""
    existing = {e for e in (existing_external_ids or []) if e}
    if last_run_at is not None and last_run_at.tzinfo is None:
        last_run_at = last_run_at.replace(tzinfo=UTC)
    threshold = last_run_at or (datetime.now(UTC) - timedelta(days=7))
    since: date = threshold.date()

    papers, stats = await discovery.fetch_all_sources(query, limit=limit, since=since)
    papers = discovery.deduplicate_papers(papers)

    new_papers = []
    for paper in papers:
        ext_id = paper.get("external_id")
        if not ext_id or ext_id in existing:
            continue
        published = paper.get("publication_date") or ""
        if published and published[:10] < since.isoformat():
            continue  # source ignored the date filter (e.g. year-only granularity)
        existing.add(ext_id)
        new_papers.append(paper)

    new_papers.sort(
        key=lambda p: p.get("publication_date") or str(p.get("year") or ""), reverse=True
    )
    new_papers = new_papers[:limit]
    return {
        "new_papers": new_papers,
        "total_new": len(new_papers),
        "is_first_run": last_run_at is None,
        "query": query,
        "threshold_date": threshold.isoformat(),
        "source_stats": stats,
    }


def generate_digest_notification(
    digest_name: str, query: str, new_papers: list[dict], frequency: str
) -> str:
    if not new_papers:
        return f"""
Orchestrix Research Digest: {digest_name}

No new papers found for your query "{query}" since the last run.

This is expected if:
- The research area is stable with few new publications
- Your search query is very specific
- The frequency is set to daily and yesterday had no new papers

To modify your digest settings, visit your Orchestrix dashboard.

---
Orchestrix - Multi-Agent Research Intelligence Platform
"""

    top_papers = new_papers[:5]

    papers_list = []
    for i, paper in enumerate(top_papers, 1):
        authors = ", ".join(paper.get("authors", ["Unknown"])[:3])
        if len(paper.get("authors", [])) > 3:
            authors += " et al."

        paper_text = f"""
{i}. {paper.get("title", "Untitled")}
   Authors: {authors}
   Year: {paper.get("year", "N/A")}
   Citations: {paper.get("citation_count", 0) or 0}
   Source: {paper.get("source", "Unknown")}
   URL: {paper.get("source_url", "N/A")}
"""
        papers_list.append(paper_text)

    more_count = len(new_papers) - 5

    return f"""
Orchestrix Research Digest: {digest_name}

New papers found for your query: "{query}"
Run frequency: {frequency}

=== Top {len(top_papers)} Papers ===

{"".join(papers_list)}

{"=" * 50}
{f"Plus {more_count} more new papers. See dashboard." if more_count > 0 else ""}
{"=" * 50}

Total new papers this digest: {len(new_papers)}

---
Orchestrix - Multi-Agent Research Intelligence Platform
"""
