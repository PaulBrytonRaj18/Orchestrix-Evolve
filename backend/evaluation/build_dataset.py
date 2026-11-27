"""Build the frozen ranking evaluation set (run manually; needs network).

For each topic:
  1. find up to three highly cited *reviews* on OpenAlex about it;
  2. run Orchestrix's own discovery for the topic → the candidate pool it would rank;
  3. a candidate is relevant when any of those reviews cites it (OpenAlex
     ``referenced_works``, matched by DOI or normalised title).

Topics whose pool contains fewer than ``MIN_RELEVANT`` cited papers are dropped. The
result is written to ``evaluation/data/eval_set.json.gz`` and scored offline by
``python -m evaluation.run``. Citation-derived relevance is a standard proxy in
citation-recommendation research: it rewards rankers that surface the papers an
expert chose, without hand labelling.

    python -m evaluation.build_dataset
"""

from __future__ import annotations

import asyncio
import gzip
import json
from pathlib import Path

import httpx

from agents import discovery

OPENALEX = "https://api.openalex.org/works"
OUT = Path(__file__).parent / "data" / "eval_set.json.gz"
MIN_RELEVANT = 3
POOL_LIMIT = 50  # per source, as in production

TOPICS = [
    "graph neural networks drug discovery",
    "transformer models natural language processing",
    "federated learning privacy",
    "reinforcement learning robotics",
    "CRISPR gene editing therapy",
    "quantum machine learning",
    "explainable artificial intelligence",
    "deep learning medical image segmentation",
    "large language models hallucination",
    "diffusion models image generation",
    "self-supervised learning computer vision",
    "recommender systems deep learning",
    "knowledge graph embedding",
    "adversarial attacks deep neural networks",
    "time series forecasting deep learning",
    "autonomous driving perception",
    "end-to-end speech recognition",
    "few-shot learning",
    "neural architecture search",
    "continual learning catastrophic forgetting",
    "machine learning materials discovery",
    "single-cell RNA sequencing analysis",
    "protein structure prediction deep learning",
    "machine learning climate change",
    "smart contract security blockchain",
    "edge computing internet of things",
    "sentiment analysis deep learning",
    "anomaly detection deep learning",
    "point cloud deep learning",
    "visual question answering",
    "domain adaptation",
    "spiking neural networks",
]

_KEEP = ("title", "abstract", "year", "citation_count", "venue", "source", "doi", "arxiv_id",
         "external_id", "authors", "publication_date")  # fmt: skip


SURVEYS_PER_TOPIC = 3


async def find_surveys(client: httpx.AsyncClient, topic: str) -> list[dict]:
    r = await client.get(
        OPENALEX,
        params={
            "search": topic,
            "filter": "type:review,cited_by_count:>50",
            "sort": "relevance_score:desc",
            "per_page": 10,
            "select": "id,title,doi,publication_year,referenced_works,referenced_works_count",
        },
    )
    r.raise_for_status()
    return [
        item for item in r.json()["results"] if (item.get("referenced_works_count") or 0) >= 40
    ][:SURVEYS_PER_TOPIC]


async def reference_keys(client: httpx.AsyncClient, ids: list[str]) -> tuple[set[str], set[str]]:
    dois, titles = set(), set()
    short = [i.rsplit("/", 1)[-1] for i in ids]
    for start in range(0, len(short), 50):
        chunk = short[start : start + 50]
        r = await client.get(
            OPENALEX,
            params={
                "filter": "openalex_id:" + "|".join(chunk),
                "per_page": 50,
                "select": "id,doi,title",
            },
        )
        r.raise_for_status()
        for w in r.json()["results"]:
            if w.get("doi"):
                dois.add(discovery.normalize_doi(w["doi"]))
            if w.get("title"):
                titles.add(discovery.normalize_text(w["title"]))
    return dois, titles


async def build() -> None:
    queries = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for topic in TOPICS:
            surveys = await find_surveys(client, topic)
            if not surveys:
                print(f"skip  {topic}: no suitable review")
                continue
            # Union of several reviews' references: several experts' choices, less bias.
            refs = sorted({w for s in surveys for w in s["referenced_works"]})
            ref_dois, ref_titles = await reference_keys(client, refs)
            papers, stats = await discovery.fetch_all_sources(topic, limit=POOL_LIMIT)
            pool = discovery.deduplicate_papers(papers)
            survey_titles = {discovery.normalize_text(s["title"]) for s in surveys}
            pool = [p for p in pool if discovery.normalize_text(p["title"]) not in survey_titles]
            for p in pool:
                p["relevant"] = bool(
                    (p.get("doi") and p["doi"] in ref_dois)
                    or discovery.normalize_text(p["title"]) in ref_titles
                )
            n_rel = sum(p["relevant"] for p in pool)
            status = {k: v["status"] for k, v in stats.items()}
            if n_rel < MIN_RELEVANT:
                print(f"skip  {topic}: {n_rel} relevant in pool of {len(pool)} {status}")
                continue
            print(
                f"keep  {topic}: {n_rel}/{len(pool)} relevant from {len(surveys)} reviews {status}"
            )
            queries.append(
                {
                    "query": topic,
                    "surveys": [
                        {
                            "title": s["title"],
                            "doi": s.get("doi"),
                            "year": s.get("publication_year"),
                        }
                        for s in surveys
                    ],
                    "reference_count": len(refs),
                    "pool": [
                        {
                            **{k: p.get(k) for k in _KEEP},
                            "abstract": (p.get("abstract") or "")[:1500],
                            "relevant": p["relevant"],
                        }
                        for p in pool
                    ],
                }
            )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        json.dump({"version": 1, "queries": queries}, fh)
    print(f"wrote {len(queries)} queries to {OUT}")


if __name__ == "__main__":
    asyncio.run(build())
