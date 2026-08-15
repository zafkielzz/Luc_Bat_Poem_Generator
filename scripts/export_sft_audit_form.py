#!/usr/bin/env python3
"""Export the Stage 1.3 corpus audit sample as an annotator-friendly CSV."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "sft" / "quality_audit_sample_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "sft" / "quality_audit_form_v1.csv"
FIELDS = [
    "audit_id", "work_id", "split", "title", "source_url", "poem",
    "naturalness_1_5", "imagery_coherence_1_5", "sensitive_or_unusable_0_1",
    "decision_accept_reject", "notes",
]


def export_form(input_path, output_path):
    rows = []
    with Path(input_path).open(encoding="utf-8") as source:
        for index, line in enumerate(source, 1):
            item = json.loads(line)
            rows.append({
                "audit_id": f"DA{index:03d}",
                "work_id": item["work_id"],
                "split": item["split"],
                "title": item["title"],
                "source_url": item["url"],
                "poem": item["text"],
                "naturalness_1_5": "",
                "imagery_coherence_1_5": "",
                "sensitive_or_unusable_0_1": "",
                "decision_accept_reject": "",
                "notes": "",
            })
    with Path(output_path).open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(f"Exported {export_form(args.input, args.output)} rows to {args.output}")


if __name__ == "__main__":
    main()
