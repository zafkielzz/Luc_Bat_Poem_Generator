#!/usr/bin/env python3
"""Prepare text-only, split-safe data for broad Luc Bat language adaptation.

This stage trains poetic language and collocations, not the Tet4 instruction
format.  It therefore keeps full poems as text-only causal-LM examples.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "quality_fsoft_v1.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "sft" / "archive" / "domain_adaptation_fsoft_v1" / "domain_adaptation_fsoft_v1"


def load_records(path):
    records = [json.loads(line) for line in Path(path).open(encoding="utf-8")]
    if not records:
        raise ValueError("No records")
    return records


def validate_split_integrity(records):
    clusters = defaultdict(set)
    work_ids = set()
    for record in records:
        if record["work_id"] in work_ids:
            raise ValueError("Duplicate work_id")
        work_ids.add(record["work_id"])
        clusters[record["duplicate_cluster"]].add(record["split"])
    if any(len(splits) != 1 for splits in clusters.values()):
        raise ValueError("Duplicate cluster leaked across splits")


def build(input_path, output_dir):
    records = load_records(input_path)
    validate_split_integrity(records)
    output_dir.mkdir(parents=True, exist_ok=True)
    split_counts, token_counts = Counter(), Counter()
    files = {split: (output_dir / f"{split}.jsonl").open("w", encoding="utf-8") for split in ("train", "dev", "test")}
    try:
        for record in sorted(records, key=lambda item: item["work_id"]):
            split = record["split"]
            if split not in files:
                raise ValueError(f"Unexpected split: {split}")
            item = {
                "text": record["text"],
                "work_id": record["work_id"],
                "duplicate_cluster": record["duplicate_cluster"],
                "source_id": record["source_id"],
            }
            files[split].write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
            split_counts[split] += 1
            token_counts[split] += len(item["text"].split())
    finally:
        for handle in files.values():
            handle.close()
    stats = {
        "version": "domain-adaptation-fsoft-v1",
        "input": str(input_path),
        "input_sha256": hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
        "source_id": "fsoft_poem_generator_mit_v1",
        "license": "MIT",
        "task": "text-only causal language modeling for broad Luc Bat poetic language",
        "explicit_exclusions": [
            "Tet4 instruction pairs",
            "Tet4 held-out prompts",
            "synthetic poems",
            "web-mined Tet4 staging",
        ],
        "split_rule": "inherited cluster-safe FSoft quality split",
        "record_counts": dict(split_counts),
        "whitespace_token_counts": dict(token_counts),
    }
    (output_dir / "manifest.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
