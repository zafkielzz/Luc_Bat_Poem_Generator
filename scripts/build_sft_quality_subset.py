#!/usr/bin/env python3
"""Stage 1.3: frozen-form quality gate and deterministic manual-audit sample."""
import argparse
import hashlib
import heapq
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DEFAULT_INPUT = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "staging_fsoft_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "quality_fsoft_v1.jsonl"
DEFAULT_STATS = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "quality_fsoft_v1_stats.json"
DEFAULT_AUDIT = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "quality_audit_sample_v1.jsonl"
TOKEN_RE = re.compile(r"[a-zA-ZÀ-ỹĐđ]+")


def longest_token_run(text):
    longest, current, previous = 0, 0, None
    for token in TOKEN_RE.findall(text.lower()):
        if token == previous:
            current += 1
        else:
            previous, current = token, 1
        longest = max(longest, current)
    return longest


def quality_decision(record, evaluator):
    evaluation = evaluator.evaluate(record["text"])
    reasons = []
    if not evaluation["structure_ok"]:
        reasons.append("structure")
    if evaluation["tcr"] < 95.0:
        reasons.append("tone")
    if evaluation["rma"] < 90.0:
        reasons.append("rhyme")
    lines = [line.strip().lower() for line in record["text"].splitlines() if line.strip()]
    if len(lines) != len(set(lines)):
        reasons.append("repeated_line")
    if longest_token_run(record["text"]) >= 4:
        reasons.append("repeated_token_run")
    return evaluation, reasons


def keep_audit_sample(heap, record, size):
    rank = int(hashlib.sha256(record["work_id"].encode()).hexdigest(), 16)
    item = (-rank, record["work_id"], record)
    if len(heap) < size:
        heapq.heappush(heap, item)
    elif item > heap[0]:
        heapq.heapreplace(heap, item)


def build(input_path, output_path, stats_path, audit_path, audit_size=100):
    from engine.evaluator import LucBatEvaluator

    evaluator = LucBatEvaluator()
    rejected = Counter()
    by_split = Counter()
    accepted = 0
    total = 0
    audit_heap = []
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with Path(input_path).open(encoding="utf-8") as source, Path(output_path).open("w", encoding="utf-8") as output:
        for line in source:
            total += 1
            record = json.loads(line)
            evaluation, reasons = quality_decision(record, evaluator)
            if reasons:
                rejected.update(reasons)
                continue
            record["quality_gate"] = {
                "version": "frozen-evaluator-v1",
                "evaluation": {
                    key: evaluation[key]
                    for key in ("scr", "tcr", "exact_rma", "slant_rma", "rma", "overall")
                },
                "rules": ["structure", "tcr>=95", "rma>=90", "no_repeated_line", "token_run<4"],
            }
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            accepted += 1
            by_split[record["split"]] += 1
            keep_audit_sample(audit_heap, record, audit_size)

    audit_rows = [item[2] for item in sorted(audit_heap, reverse=True)]
    with Path(audit_path).open("w", encoding="utf-8") as handle:
        for row in audit_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    stats = {
        "version": "sft-quality-v1",
        "input": str(input_path),
        "input_rows": total,
        "accepted_rows": accepted,
        "acceptance_rate": round(accepted / total, 6) if total else 0.0,
        "accepted_by_split": dict(by_split),
        "rejection_reason_counts": dict(rejected),
        "quality_gate": {
            "evaluator": "frozen-evaluator-v1",
            "structure": "required",
            "min_tcr": 95.0,
            "min_rma": 90.0,
            "max_repeated_token_run": 3,
        },
        "manual_audit": {
            "path": str(audit_path),
            "n": len(audit_rows),
            "selection": "deterministic lowest SHA-256 work_id ranks among accepted rows",
        },
    }
    Path(stats_path).write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--audit-size", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output, args.stats, args.audit, args.audit_size), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
