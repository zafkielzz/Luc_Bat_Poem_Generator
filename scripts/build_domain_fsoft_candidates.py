#!/usr/bin/env python3
"""Build a provenance-preserving Xuân–Tết domain-adaptation candidate set.

This produces candidates only.  A separate frozen quality gate and human audit
must pass before the records are used for QLoRA domain adaptation.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from scripts.build_sft_staging import ROOT, cluster_rows, load_luc_bat_rows

DEFAULT_INPUT = ROOT / "data" / "raw" / "fsoft_poem_generator_mit_v1" / "poems_dataset.csv"
DEFAULT_OUTPUT = ROOT / "data" / "sft" / "domain_fsoft_candidates_v1.jsonl"
DEFAULT_STATS = ROOT / "data" / "sft" / "domain_fsoft_candidates_v1_stats.json"

SIGNAL_PATTERNS = {
    "tet_direct": re.compile(
        r"\b(tết|giao thừa|năm mới|tân niên|nguyên đán|lì xì|mừng tuổi|bánh chưng|bánh tét)\b",
        re.I,
    ),
    "spring_explicit": re.compile(
        r"\b(mùa xuân|xuân|hoa đào|hoa mai|chồi non|cánh én|mưa xuân|nắng xuân)\b",
        re.I,
    ),
    "reunion": re.compile(r"\b(đoàn viên|sum vầy|sum họp|quây quần|gia đình)\b", re.I),
}
SELECTION_RULE = "tet_direct OR (spring_explicit AND reunion)"


def is_domain_record(text):
    signals = [name for name, pattern in SIGNAL_PATTERNS.items() if pattern.search(text)]
    return "tet_direct" in signals or {"spring_explicit", "reunion"}.issubset(signals), signals


def build(input_path, output_path, stats_path):
    rows, genres = load_luc_bat_rows(input_path)
    selected, signal_counts = [], Counter()
    for row in rows:
        keep, signals = is_domain_record(row["text"])
        if not keep:
            continue
        row["domain_signals"] = signals
        row["domain_selection_rule"] = SELECTION_RULE
        selected.append(row)
        signal_counts.update(signals)
    staged, dedup_stats = cluster_rows(selected)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in sorted(staged, key=lambda item: item["work_id"]):
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    stats = {
        "version": "domain-fsoft-candidates-v1",
        "input": str(input_path),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "source_id": "fsoft_poem_generator_mit_v1",
        "license": "MIT",
        "selection_rule": "genre == luc bat AND (" + SELECTION_RULE + ")",
        "signal_patterns": {name: pattern.pattern for name, pattern in SIGNAL_PATTERNS.items()},
        "raw_selected_rows": len(selected),
        "raw_selected_whitespace_tokens": sum(len(row["text"].split()) for row in selected),
        "staged_whitespace_tokens": sum(len(row["text"].split()) for row in staged),
        "signal_match_counts": dict(signal_counts),
        "genre_counts": dict(genres),
        **dedup_stats,
    }
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output, args.stats), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
