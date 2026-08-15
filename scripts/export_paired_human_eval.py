#!/usr/bin/env python3
"""Export side-by-side, blind paired comparisons for baseline versus SFT."""
import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.export_human_eval_bundle import load_pairs, stratified_select


def export_paired_bundle(baseline_path: Path, sft_path: Path, out_dir: Path, count: int, seed: int,
                         prompt_ids=None, version="pilot-human-eval-paired-v1"):
    all_pairs = load_pairs(baseline_path, sft_path)
    if prompt_ids:
        by_id = {pair["prompt_id"]: pair for pair in all_pairs}
        missing = [prompt_id for prompt_id in prompt_ids if prompt_id not in by_id]
        if missing:
            raise ValueError(f"Không có prompt_id: {', '.join(missing)}")
        if len(set(prompt_ids)) != len(prompt_ids):
            raise ValueError("prompt_ids không được trùng")
        pairs = [by_id[prompt_id] for prompt_id in prompt_ids]
        if count != len(pairs):
            raise ValueError("count phải bằng số prompt_ids đã chọn")
    else:
        pairs = stratified_select(all_pairs, count)
    rng = random.Random(seed)
    rng.shuffle(pairs)
    out_dir.mkdir(parents=True, exist_ok=True)
    form_path = out_dir / "paired_ratings_template.csv"
    key_path = out_dir / "paired_blind_key.json"
    fields = [
        "pair_id", "prompt_id", "prompt", "num_lines", "poem_A", "poem_B",
        "preference", "strength", "notes",
    ]
    key_items = []
    with form_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, pair in enumerate(pairs, 1):
            variants = ["baseline", "sft"]
            rng.shuffle(variants)
            pair_id = f"P{index:02d}"
            writer.writerow({
                "pair_id": pair_id,
                "prompt_id": pair["prompt_id"],
                "prompt": pair["prompt"],
                "num_lines": pair["num_lines"],
                "poem_A": pair[variants[0]],
                "poem_B": pair[variants[1]],
                "preference": "",
                "strength": "",
                "notes": "",
            })
            key_items.append({
                "pair_id": pair_id,
                "prompt_id": pair["prompt_id"],
                "A": variants[0],
                "B": variants[1],
            })
    key_path.write_text(json.dumps({
        "version": version,
        "seed": seed,
        "prompt_count": len(pairs),
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
    parser.add_argument("--prompt-ids", default=None,
                        help="Danh sách prompt ID cách nhau bởi dấu phẩy; giữ thứ tự trước khi xáo A/B")
    parser.add_argument("--version", default="pilot-human-eval-paired-v1")
    args = parser.parse_args()
    prompt_ids = [item.strip() for item in args.prompt_ids.split(",") if item.strip()] if args.prompt_ids else None
    form_path, key_path = export_paired_bundle(
        args.baseline, args.sft, args.out_dir, args.count, args.seed,
        prompt_ids=prompt_ids, version=args.version,
    )
    print(f"form={form_path}")
    print(f"blind_key={key_path}")


if __name__ == "__main__":
    main()
