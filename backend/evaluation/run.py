"""Score ranking strategies on the frozen evaluation set.

    python -m evaluation.run                       # TF-IDF baseline + configured model
    python -m evaluation.run --models all          # every supported embedding model
    python -m evaluation.run --models all --tune   # + cross-validated weight search

Metrics (averaged over queries): nDCG@20, Recall@20, MRR. Weight tuning uses 2-fold
cross-validation: weights are chosen on one half of the queries and scored on the
other, so the reported number is not fitted to the data it is measured on.
"""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
import math
from pathlib import Path

import numpy as np

from agents import discovery
from agents.discovery import RankWeights, ranking_features, score_features

DATA = Path(__file__).parent / "data" / "eval_set.json.gz"
K = 20


# ─── metrics ─────────────────────────────────────────────────────────────────


def ndcg_at_k(rels: list[bool], k: int = K) -> float:
    dcg = sum(1.0 / math.log2(i + 2) for i, r in enumerate(rels[:k]) if r)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(sum(rels), k)))
    return dcg / ideal if ideal else 0.0


def recall_at_k(rels: list[bool], k: int = K) -> float:
    total = sum(rels)
    return sum(rels[:k]) / total if total else 0.0


def mrr(rels: list[bool]) -> float:
    return next((1.0 / (i + 1) for i, r in enumerate(rels) if r), 0.0)


def evaluate(rankings: list[list[bool]]) -> dict[str, float]:
    n = len(rankings)
    return {
        "ndcg@20": sum(ndcg_at_k(r) for r in rankings) / n,
        "recall@20": sum(recall_at_k(r) for r in rankings) / n,
        "mrr": sum(mrr(r) for r in rankings) / n,
    }


# ─── data ────────────────────────────────────────────────────────────────────


def load_queries() -> list[dict]:
    with gzip.open(DATA, "rt", encoding="utf-8") as fh:
        return json.load(fh)["queries"]


def _minmax(values: np.ndarray) -> np.ndarray:
    lo, hi = float(values.min()), float(values.max())
    return (values - lo) / (hi - lo) if hi > lo else np.full_like(values, 0.5)


def dense_scores(queries: list[dict], model_name: str, max_chars: int) -> list[np.ndarray]:
    """Per-pool cosine similarity, min-max scaled to [0, 1]."""
    from services.embeddings import Embedder, document_text

    embedder = Embedder(model_name)
    out = []
    for q in queries:
        docs = embedder.embed_documents([document_text(p, max_chars) for p in q["pool"]])
        out.append(_minmax(docs @ embedder.embed_query(q["query"])))
    return out


def features_for(queries: list[dict], semantic: list[np.ndarray] | None) -> list[list[dict]]:
    """Feature dicts per pool. ``semantic=None`` → production TF-IDF similarity."""
    result = []
    for qi, q in enumerate(queries):
        pool = [dict(p) for p in q["pool"]]
        if semantic is None:
            discovery.compute_semantic_similarity(q["query"], pool)
        else:
            for p, s in zip(pool, semantic[qi], strict=True):
                p["semantic_score"] = float(s)
        max_c = max((p.get("citation_count") or 0) for p in pool)
        years = [p["year"] for p in pool if p.get("year")] or [2020]
        result.append(
            [ranking_features(p, q["query"], max_c, min(years), max(years)) for p in pool]
        )
    return result


def rank_with(
    queries: list[dict], feats: list[list[dict]], weights: RankWeights, idx: list[int] | None = None
) -> list[list[bool]]:
    rankings = []
    for qi in idx if idx is not None else range(len(queries)):
        scored = [
            (score_features(f, weights), p["relevant"])
            for f, p in zip(feats[qi], queries[qi]["pool"], strict=True)
        ]
        scored.sort(key=lambda t: t[0], reverse=True)
        rankings.append([rel for _, rel in scored])
    return rankings


def weight_grid() -> list[RankWeights]:
    grid = []
    for sem, kw, cit, rec, ven in itertools.product(
        (0.3, 0.45, 0.6, 0.75),
        (0.0, 0.1, 0.2),
        (0.0, 0.1, 0.25),
        (0.0, 0.05, 0.1),
        (0.0, 0.05, 0.1),
    ):
        grid.append(RankWeights(sem, kw, cit, rec, ven))
    return grid


def cross_validated(queries, feats) -> tuple[dict[str, float], list[RankWeights]]:
    """2-fold CV: pick the best grid weights on one fold, score them on the other."""
    folds = [list(range(0, len(queries), 2)), list(range(1, len(queries), 2))]
    held_out: list[list[bool]] = []
    chosen = []
    grid = weight_grid()
    for train, test in ((folds[0], folds[1]), (folds[1], folds[0])):
        best = max(grid, key=lambda w: evaluate(rank_with(queries, feats, w, train))["ndcg@20"])
        chosen.append(best)
        held_out.extend(rank_with(queries, feats, best, test))
    return evaluate(held_out), chosen


def main() -> None:
    from services.embeddings import MODELS

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--variants",
        default="BAAI/bge-small-en-v1.5@600",
        help="comma-separated model@max_chars, e.g. BAAI/bge-small-en-v1.5@600",
    )
    parser.add_argument("--tune", action="store_true")
    args = parser.parse_args()
    queries = load_queries()
    n_rel = sum(p["relevant"] for q in queries for p in q["pool"])
    n_pool = sum(len(q["pool"]) for q in queries)
    print(f"{len(queries)} queries · {n_pool} candidates · {n_rel} relevant\n")

    rows: list[tuple[str, dict[str, float]]] = []
    rng = np.random.default_rng(0)
    rows.append(
        (
            "random order",
            evaluate([list(rng.permutation([p["relevant"] for p in q["pool"]])) for q in queries]),
        )
    )
    tfidf = features_for(queries, None)
    rows.append(
        ("TF-IDF hybrid (production before)", evaluate(rank_with(queries, tfidf, RankWeights())))
    )
    rows.append(("citations only", evaluate(rank_with(queries, tfidf, RankWeights(0, 0, 1, 0, 0)))))

    for variant in args.variants.split(","):
        name, _, chars = variant.partition("@")
        if name not in MODELS:
            raise SystemExit(f"unknown model {name}")
        sem = dense_scores(queries, name, int(chars or 600))
        feats = features_for(queries, sem)
        short = f"{name.split('/')[-1]}@{chars or 600}"
        rows.append(
            (
                f"{short}: dense only",
                evaluate(rank_with(queries, feats, RankWeights(1, 0, 0, 0, 0))),
            )
        )
        rows.append(
            (
                f"{short}: hybrid, default weights",
                evaluate(rank_with(queries, feats, RankWeights())),
            )
        )
        if args.tune:
            metrics, chosen = cross_validated(queries, feats)
            rows.append((f"{short}: hybrid, CV-tuned weights", metrics))
            print(f"{short} weights chosen per fold: {chosen}")

    print(f"\n{'strategy':<48}{'nDCG@20':>9}{'R@20':>8}{'MRR':>8}")
    for label, m in rows:
        print(f"{label:<48}{m['ndcg@20']:>9.3f}{m['recall@20']:>8.3f}{m['mrr']:>8.3f}")


if __name__ == "__main__":
    main()
