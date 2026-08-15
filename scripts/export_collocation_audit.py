#!/usr/bin/env python3
"""Export a blinded, development-only audit for a collocation diagnostic."""
import argparse
import csv
import json
import random
from pathlib import Path

from analyze_collocation import build_counts, poem_metrics


def candidate_pair(candidates, unigram, bigram, vocabulary, alpha, rare_cutoff):
    scored = []
    for index, candidate in enumerate(candidates):
        metric = poem_metrics(
            candidate["poem"], unigram, bigram, vocabulary, alpha, rare_cutoff
        )
        if metric["mean_conditional_logprob"] is None:
            continue
        scored.append({"index": index, "candidate": candidate, "metric": metric})

    # Keep rule-compliance broadly comparable so the audit asks about naturalness.
    options = []
    for high in scored:
        for low in scored:
            if high["index"] == low["index"]:
                continue
            high_overall = high["candidate"]["eval"]["overall"]
            low_overall = low["candidate"]["eval"]["overall"]
            if abs(high_overall - low_overall) <= 10 and \
                    high["metric"]["mean_conditional_logprob"] > low["metric"]["mean_conditional_logprob"]:
                options.append((
                    high["metric"]["mean_conditional_logprob"] - low["metric"]["mean_conditional_logprob"],
                    high, low,
                ))
    if not options:
        return None
    _, high, low = max(options, key=lambda item: item[0])
    return high, low


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Export a blind collocation audit from development candidates")
    parser.add_argument("--corpus", type=Path, default=root / "data/sft/quality_fsoft_v1.jsonl")
    parser.add_argument("--ablation", type=Path,
                        default=root / "experiments/evaluation_freeze_v1/ablation_stage0_seed42_n50.json")
    parser.add_argument("--out-dir", type=Path, default=root / "data/evaluation/collocation_audit_v1")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260810)
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--rare-cutoff", type=int, default=1)
    args = parser.parse_args()

    unigram, bigram, _ = build_counts(args.corpus)
    artifact = json.loads(args.ablation.read_text(encoding="utf-8"))
    items = []
    for pool in artifact["candidate_pools"]:
        pair = candidate_pair(
            pool["engine"], unigram, bigram, len(unigram), args.alpha, args.rare_cutoff
        )
        if pair is None:
            continue
        high, low = pair
        items.append({
            "prompt": pool["prompt"],
            "high": high,
            "low": low,
            "gap": high["metric"]["mean_conditional_logprob"] - low["metric"]["mean_conditional_logprob"],
        })
    if len(items) < args.count:
        raise ValueError(f"Chỉ tìm được {len(items)} pair đủ điều kiện")

    # Select the clearest diagnostic differences, then randomize display and A/B side.
    rng = random.Random(args.seed)
    selected = sorted(items, key=lambda item: item["gap"], reverse=True)[:args.count]
    rng.shuffle(selected)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    form_path = args.out_dir / "ratings_template.csv"
    key_path = args.out_dir / "blind_key.json"
    fields = ["pair_id", "prompt", "poem_A", "poem_B", "preference", "notes"]
    key_items = []
    with form_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for number, item in enumerate(selected, 1):
            sides = ["high_collocation", "low_collocation"]
            rng.shuffle(sides)
            poems = {
                "high_collocation": item["high"]["candidate"]["poem"],
                "low_collocation": item["low"]["candidate"]["poem"],
            }
            pair_id = f"C{number:02d}"
            writer.writerow({
                "pair_id": pair_id,
                "prompt": item["prompt"],
                "poem_A": poems[sides[0]],
                "poem_B": poems[sides[1]],
                "preference": "",
                "notes": "",
            })
            key_items.append({
                "pair_id": pair_id,
                "A": sides[0],
                "B": sides[1],
                "high_candidate_index": item["high"]["index"],
                "low_candidate_index": item["low"]["index"],
                "logprob_gap": round(item["gap"], 4),
            })
    key_path.write_text(json.dumps({
        "version": "collocation-audit-v1",
        "purpose": "development-only diagnostic; do not use held-out prompts",
        "seed": args.seed,
        "items": key_items,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"form={form_path}")
    print(f"blind_key={key_path}")


if __name__ == "__main__":
    main()
