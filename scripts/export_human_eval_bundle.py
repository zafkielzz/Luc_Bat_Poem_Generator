#!/usr/bin/env python3
"""Export a reproducible blind baseline-vs-SFT human-evaluation bundle."""
import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path


RATING_COLUMNS = [
    "form_accuracy",
    "naturalness",
    "imagery_emotion",
    "topic_fit",
    "cliche_restraint",
]


def load_pairs(baseline_path: Path, sft_path: Path):
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    sft = json.loads(sft_path.read_text(encoding="utf-8"))
    base_rows = {row.get("prompt_id", row["prompt"]): row for row in baseline}
    sft_rows = {row.get("prompt_id", row["prompt"]): row for row in sft}
    if set(base_rows) != set(sft_rows):
        raise ValueError("Baseline và SFT không cùng tập prompt")
    pairs = []
    for prompt_id in sorted(base_rows):
        base, tuned = base_rows[prompt_id], sft_rows[prompt_id]
        if base["prompt"] != tuned["prompt"]:
            raise ValueError(f"Prompt không khớp: {prompt_id}")
        pairs.append({
            "prompt_id": prompt_id,
            "prompt": base["prompt"],
            "num_lines": base["metadata"]["số câu"],
            "baseline": base["candidates"][0]["poem"],
            "sft": tuned["candidates"][0]["poem"],
        })
    return pairs


def stratified_select(pairs, count):
    if count < 1 or count > len(pairs):
        raise ValueError(f"count phải trong khoảng 1..{len(pairs)}")
    groups = defaultdict(list)
    for pair in pairs:
        groups[pair["num_lines"]].append(pair)
    lengths = sorted(groups)
    selected = []
    for index, length in enumerate(lengths):
        target = count // len(lengths) + (1 if index < count % len(lengths) else 0)
        selected.extend(groups[length][:target])
    if len(selected) < count:
        chosen = {pair["prompt_id"] for pair in selected}
        selected.extend(pair for pair in pairs if pair["prompt_id"] not in chosen)
    return selected[:count]


def export_bundle(baseline_path: Path, sft_path: Path, out_dir: Path, count: int, seed: int):
    pairs = stratified_select(load_pairs(baseline_path, sft_path), count)
    items = []
    for pair in pairs:
        for variant in ("baseline", "sft"):
            items.append({**pair, "variant": variant, "poem": pair[variant]})
    random.Random(seed).shuffle(items)
    out_dir.mkdir(parents=True, exist_ok=True)
    form_path = out_dir / "ratings_template.csv"
    key_path = out_dir / "blind_key.json"
    fields = ["item_id", "prompt_id", "prompt", "num_lines", "poem", *RATING_COLUMNS, "notes"]
    key_items = []
    with form_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, item in enumerate(items, 1):
            item_id = f"H{index:02d}"
            writer.writerow({
                "item_id": item_id,
                "prompt_id": item["prompt_id"],
                "prompt": item["prompt"],
                "num_lines": item["num_lines"],
                "poem": item["poem"],
                **{column: "" for column in RATING_COLUMNS},
                "notes": "",
            })
            key_items.append({"item_id": item_id, "prompt_id": item["prompt_id"], "variant": item["variant"]})
    key_path.write_text(json.dumps({
        "version": "pilot-human-eval-v1",
        "seed": seed,
        "prompt_count": len(pairs),
        "item_count": len(items),
        "baseline_candidates": str(baseline_path),
        "sft_candidates": str(sft_path),
        "items": key_items,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return form_path, key_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--sft", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    form_path, key_path = export_bundle(args.baseline, args.sft, args.out_dir, args.count, args.seed)
    print(f"form={form_path}")
    print(f"blind_key={key_path}")


if __name__ == "__main__":
    main()
