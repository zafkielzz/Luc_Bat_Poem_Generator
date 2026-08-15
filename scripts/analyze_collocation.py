#!/usr/bin/env python3
"""CPU-only collocation diagnostic; it never modifies decoding or reranker weights."""
import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path


WORD_RE = re.compile(r"[a-zà-ỹđ]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def build_counts(corpus_path: Path) -> tuple[Counter, Counter, int]:
    unigram, bigram = Counter(), Counter()
    with corpus_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            for verse in record["text"].splitlines():
                words = tokenize(verse)
                unigram.update(words)
                bigram.update(zip(words, words[1:]))
    return unigram, bigram, sum(unigram.values())


def poem_metrics(poem: str, unigram: Counter, bigram: Counter, vocabulary: int,
                 alpha: float, rare_cutoff: int) -> dict:
    pairs = []
    for line in poem.splitlines():
        words = tokenize(line)
        pairs.extend(zip(words, words[1:]))
    if not pairs:
        return {"pair_count": 0, "mean_conditional_logprob": None,
                "unseen_rate": None, "rare_rate": None, "lowest_bigrams": []}

    scored = []
    for left, right in pairs:
        count = bigram[(left, right)]
        probability = (count + alpha) / (unigram[left] + alpha * vocabulary)
        scored.append({
            "bigram": f"{left} {right}",
            "count": count,
            "logprob": math.log(probability),
        })
    scored.sort(key=lambda item: (item["count"], item["logprob"]))
    return {
        "pair_count": len(scored),
        "mean_conditional_logprob": round(
            sum(item["logprob"] for item in scored) / len(scored), 4
        ),
        "unseen_rate": round(sum(item["count"] == 0 for item in scored) / len(scored), 4),
        "rare_rate": round(sum(item["count"] <= rare_cutoff for item in scored) / len(scored), 4),
        "lowest_bigrams": scored[:5],
    }


def aggregate(items: list[dict]) -> dict:
    usable = [item for item in items if item["pair_count"]]
    if not usable:
        return {"n": 0}
    return {
        "n": len(usable),
        "mean_conditional_logprob": round(
            sum(item["mean_conditional_logprob"] for item in usable) / len(usable), 4
        ),
        "mean_unseen_rate": round(sum(item["unseen_rate"] for item in usable) / len(usable), 4),
        "mean_rare_rate": round(sum(item["rare_rate"] for item in usable) / len(usable), 4),
    }


def score_ablation(artifact_path: Path, unigram: Counter, bigram: Counter,
                   vocabulary: int, alpha: float, rare_cutoff: int) -> dict:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    pools = artifact["candidate_pools"]
    variants = {}
    for name in ("free_gen", "engine"):
        rows = []
        for pool in pools:
            for candidate in pool[name]:
                rows.append({
                    "prompt": pool["prompt"],
                    "candidate_index": candidate.get("candidate_index"),
                    "poem": candidate["poem"],
                    "metrics": poem_metrics(
                        candidate["poem"], unigram, bigram, vocabulary, alpha, rare_cutoff
                    ),
                })
        variants[name] = {"aggregate": aggregate([row["metrics"] for row in rows]), "rows": rows}
    return {
        "artifact": str(artifact_path),
        "protocol_version": artifact.get("meta", {}).get("protocol_version"),
        "variants": variants,
    }


def normalize_choice(row: dict) -> str | None:
    direct = row.get("preference", "").strip().upper()
    if direct in {"A", "B", "TIE"}:
        return direct
    note = row.get("notes", "").strip().upper()
    if note.startswith("A"):
        return "A"
    if note.startswith("B"):
        return "B"
    return None


def score_human_pairs(form_path: Path, unigram: Counter, bigram: Counter,
                      vocabulary: int, alpha: float, rare_cutoff: int) -> dict:
    rows = list(csv.DictReader(form_path.open(encoding="utf-8", newline="")))
    comparisons = []
    for row in rows:
        choice = normalize_choice(row)
        if choice not in {"A", "B"}:
            continue
        a = poem_metrics(row["poem_A"], unigram, bigram, vocabulary, alpha, rare_cutoff)
        b = poem_metrics(row["poem_B"], unigram, bigram, vocabulary, alpha, rare_cutoff)
        # Higher log probability and lower unseen rate are better under this diagnostic.
        a_better = a["mean_conditional_logprob"] > b["mean_conditional_logprob"]
        predicted = "A" if a_better else "B"
        comparisons.append({
            "pair_id": row["pair_id"],
            "human_preference": choice,
            "collocation_preference": predicted,
            "agreement": choice == predicted,
            "A": a,
            "B": b,
        })
    return {
        "form": str(form_path),
        "n": len(comparisons),
        "agreement_n": sum(row["agreement"] for row in comparisons),
        "agreement_rate": round(sum(row["agreement"] for row in comparisons) / len(comparisons), 4)
        if comparisons else None,
        "comparisons": comparisons,
    }


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Analyze word-collocation diagnostics without changing the model")
    parser.add_argument("--corpus", type=Path, default=root / "data/sft/quality_fsoft_v1.jsonl")
    parser.add_argument("--ablation", type=Path,
                        default=root / "experiments/evaluation_freeze_v1/ablation_stage0_seed42_n50.json")
    parser.add_argument("--human-form", type=Path,
                        default=root / "data/evaluation/Bảng tính không có tiêu đề - paired_ratings_template.csv")
    parser.add_argument("--output", type=Path,
                        default=root / "experiments/collocation_diagnostic_v1.json")
    parser.add_argument("--alpha", type=float, default=0.1, help="Additive smoothing; not a tuning parameter")
    parser.add_argument("--rare-cutoff", type=int, default=1)
    args = parser.parse_args()

    unigram, bigram, token_count = build_counts(args.corpus)
    vocabulary = len(unigram)
    report = {
        "version": "collocation-diagnostic-v1",
        "purpose": "diagnostic only; no decoder or reranker weights changed",
        "reference_corpus": str(args.corpus),
        "corpus": {
            "tokens": token_count,
            "vocabulary": vocabulary,
            "distinct_bigrams": len(bigram),
            "alpha": args.alpha,
            "rare_cutoff": args.rare_cutoff,
        },
        "ablation": score_ablation(
            args.ablation, unigram, bigram, vocabulary, args.alpha, args.rare_cutoff
        ),
        "human_pair_diagnostic": score_human_pairs(
            args.human_form, unigram, bigram, vocabulary, args.alpha, args.rare_cutoff
        ),
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, item in report["ablation"]["variants"].items():
        print(name, item["aggregate"])
    print("human_pair_diagnostic", {
        key: report["human_pair_diagnostic"][key]
        for key in ("n", "agreement_n", "agreement_rate")
    })
    print(f"saved={args.output}")


if __name__ == "__main__":
    main()
