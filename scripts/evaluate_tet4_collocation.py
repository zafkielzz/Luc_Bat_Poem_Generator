#!/usr/bin/env python3
"""Ablation rank-collocation offline trên candidate Tet4 đã sinh."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.collocation import CollocationScorer
from engine.evaluator import LucBatEvaluator
from engine.reranker import LucBatReranker
from scripts.generate_poem import load_cliches


def aggregate(selected):
    return {key: round(sum(item["eval"][key] for item in selected) / len(selected), 3)
            for key in ("scr", "tcr", "rma", "overall")}


def pick(pool, weight):
    usable = [item for item in pool if not item["lexical"]["hard_fail"]]
    if not usable:
        usable = pool
    ranked = sorted(enumerate(usable), key=lambda pair: pair[1]["collocation_raw"])
    denominator = max(1, len(ranked) - 1)
    rank = {index: position / denominator for position, (index, _) in enumerate(ranked)}
    return max(enumerate(usable), key=lambda pair: pair[1]["score"] + weight * rank[pair[0]])[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, nargs="+", required=True)
    parser.add_argument("--asset", type=Path, default=ROOT / "data/assets/collocation_fsoft_quality_v1.json")
    parser.add_argument("--weights", type=float, nargs="+", default=[0.0, 0.025, 0.05, 0.1])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    scorer = CollocationScorer.load(args.asset)
    reranker = LucBatReranker(LucBatEvaluator(), load_cliches(), lexical_guard=True)
    pools = []
    for path in args.candidates:
        for record in json.loads(path.read_text(encoding="utf-8")):
            rows = reranker.rerank([item["poem"] for item in record["candidates"]], record["metadata"])
            for row in rows:
                row["collocation_raw"] = scorer.raw_score(row["poem"])
            pools.append({"source": str(path), "prompt_id": record.get("prompt_id"), "rows": rows})
    result = {"version": "tet4-rank-collocation-dev-v1", "pool_count": len(pools),
              "asset": str(args.asset), "weights": {}}
    baseline = [pick(pool["rows"], 0.0) for pool in pools]
    for weight in args.weights:
        selected = [pick(pool["rows"], weight) for pool in pools]
        changes = sum(a["poem"] != b["poem"] for a, b in zip(baseline, selected))
        result["weights"][str(weight)] = {"metrics": aggregate(selected), "selection_changes": changes}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
