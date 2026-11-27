"""Score the contradiction judge on hand-labelled claim pairs.

    python -m evaluation.claims_eval            # LLM judge if GROQ_API_KEY is set, else heuristic
    python -m evaluation.claims_eval --heuristic

Reports precision / recall / F1 for the "contradiction" label and the confusion matrix.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from agents.claims import claim_direction, heuristic_judgement, judge_pairs
from llm import get_llm

DATA = Path(__file__).parent / "data" / "claim_pairs.json"


def _as_claim(text: str) -> dict:
    return {"text": text, "evidence": text, "direction": claim_direction(text)}


def score(predicted: list[bool], gold: list[bool]) -> dict[str, float]:
    tp = sum(p and g for p, g in zip(predicted, gold, strict=True))
    fp = sum(p and not g for p, g in zip(predicted, gold, strict=True))
    fn = sum(g and not p for p, g in zip(predicted, gold, strict=True))
    tn = len(gold) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--heuristic", action="store_true")
    args = parser.parse_args()
    pairs = json.loads(DATA.read_text())["pairs"]
    gold = [p["label"] == "contradiction" for p in pairs]
    built = [(_as_claim(p["a"]), _as_claim(p["b"]), 0.9) for p in pairs]
    if args.heuristic or not get_llm().enabled:
        mode = "heuristic"
        verdicts = [heuristic_judgement(a, b, s) for a, b, s in built]
    else:
        mode = f"llm ({get_llm().model})"
        verdicts = await judge_pairs(built)
    predicted = [v["relation"] == "contradiction" for v in verdicts]
    m = score(predicted, gold)
    print(f"judge: {mode} · {len(pairs)} pairs")
    print(
        f"precision {m['precision']:.2f} · recall {m['recall']:.2f} · F1 {m['f1']:.2f}  "
        f"(tp {m['tp']}, fp {m['fp']}, fn {m['fn']}, tn {m['tn']})"
    )
    for p, v, g in zip(pairs, verdicts, gold, strict=True):
        if (v["relation"] == "contradiction") != g:
            print(
                f"  MISS gold={'contra' if g else 'not'} got={v['relation']}: {p['a'][:60]} | {p['b'][:60]}"
            )


if __name__ == "__main__":
    asyncio.run(main())
