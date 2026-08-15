#!/usr/bin/env python3
"""Validate and summarize Stage 1.3 human corpus-audit ratings."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "sft" / "quality_audit_form_v1.csv"
DEFAULT_OUTPUT = ROOT / "data" / "sft" / "quality_audit_results_v1.json"


def parse_int(value, field, allowed):
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{field} is missing or invalid") from error
    if parsed not in allowed:
        raise ValueError(f"{field} must be one of {sorted(allowed)}")
    return parsed


def analyze(input_path):
    rows = list(csv.DictReader(Path(input_path).open(encoding="utf-8", newline="")))
    if not rows:
        raise ValueError("No audit rows")
    decisions = Counter()
    naturalness, imagery, sensitive = [], [], []
    for row in rows:
        naturalness.append(parse_int(row["naturalness_1_5"], "naturalness_1_5", set(range(1, 6))))
        imagery.append(parse_int(row["imagery_coherence_1_5"], "imagery_coherence_1_5", set(range(1, 6))))
        sensitive.append(parse_int(row["sensitive_or_unusable_0_1"], "sensitive_or_unusable_0_1", {0, 1}))
        decision = row["decision_accept_reject"].strip().lower()
        if decision not in {"accept", "reject"}:
            raise ValueError("decision_accept_reject must be accept or reject")
        decisions[decision] += 1
    accepted = decisions["accept"]
    return {
        "n": len(rows),
        "accepted": accepted,
        "rejected": decisions["reject"],
        "acceptance_rate": round(accepted / len(rows), 4),
        "mean_naturalness": round(sum(naturalness) / len(rows), 3),
        "mean_imagery_coherence": round(sum(imagery) / len(rows), 3),
        "sensitive_or_unusable_n": sum(sensitive),
        "pilot_gate_passed": accepted >= 0.8 * len(rows),
        "pilot_gate": "at least 80 percent accept",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = analyze(args.input)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
