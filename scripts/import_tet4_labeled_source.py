#!/usr/bin/env python3
"""Import user-pasted Tet4 sources with explicit poem boundaries.

Long poems are split only into non-overlapping four-line blocks.  Every derived
block keeps its parent-poem ID and neighbouring context, and is exported for
human review rather than added to SFT staging.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SOURCE_RE = re.compile(r"^nguồn\s*:\s*(https?://\S+)", re.I)
CATEGORY_RE = re.compile(r"^thơ\s+chúc\s+tết\b", re.I)
ITEM_RE = re.compile(r"^(?:bài(?:\s+thơ)?\s*)?(\d+)\.?\s*$", re.I)


def clean(line: str) -> str:
    return unicodedata.normalize("NFC", line).replace("\ufeff", "").strip().strip('“”"')


def parse(path: Path):
    url = None
    category = None
    label = None
    lines: list[str] = []

    def flush():
        nonlocal lines
        if url and lines:
            yield {"url": url, "category": category, "label": label, "lines": lines}
        lines = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = clean(raw)
        source = SOURCE_RE.match(line)
        if source:
            yield from flush()
            url, category, label = source.group(1), None, None
            continue
        if not line or set(line) == {"-"}:
            yield from flush()
            continue
        if CATEGORY_RE.match(line):
            yield from flush()
            category, label = line, None
            continue
        item = ITEM_RE.match(line)
        if item:
            yield from flush()
            label = "Bài " + item.group(1)
            continue
        if line.lower().startswith("bài thơ chúc tết"):
            yield from flush()
            label = line
            continue
        if url:
            lines.append(line)
    yield from flush()


def block_kind(index: int, total_blocks: int, full_lines: int) -> str:
    if full_lines == 4:
        return "native_four_line"
    if index == 0:
        return "derived_leading"
    if index == total_blocks - 1 and full_lines % 4 == 0:
        return "derived_trailing"
    return "derived_interior"


def make_rows(poem: dict, evaluator, lexical_assess):
    lines = poem["lines"]
    parent_text = "\n".join(lines)
    parent_key = "|".join([poem["url"], poem.get("category") or "", poem.get("label") or "", parent_text])
    poem_work_id = "pasted-poem:" + hashlib.sha256(parent_key.encode()).hexdigest()[:20]
    full_blocks = len(lines) // 4
    for block_index in range(full_blocks):
        start = block_index * 4
        block_lines = lines[start:start + 4]
        text = "\n".join(block_lines)
        metrics = evaluator.evaluate(text, expected_num_lines=4)
        lexical = lexical_assess(text)
        yield {
            "candidate_id": f"{poem_work_id}:block-{block_index + 1}",
            "poem_work_id": poem_work_id,
            "source_id": "tet4_labeled_user_paste_v1",
            "url": poem["url"],
            "category": poem.get("category"),
            "source_label": poem.get("label"),
            "author": None,
            "full_line_count": len(lines),
            "block_index": block_index + 1,
            "segment_kind": block_kind(block_index, full_blocks, len(lines)),
            "context_before": "\n".join(lines[:start]),
            "text": text,
            "context_after": "\n".join(lines[start + 4:]),
            "remainder_line_count": len(lines) % 4,
            "metrics": {key: metrics[key] for key in ("scr", "tcr", "rma", "combined_rma", "structure_ok", "is_valid_lucbat")},
            "lexical_issues": lexical["issues"],
            "review_decision": "",
            "review_notes": "",
            "usage": "review_only_not_for_tet4_sft",
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    from engine.evaluator import LucBatEvaluator
    from engine.lexical_guard import assess

    poems = list(parse(args.input))
    evaluator = LucBatEvaluator()
    rows = [row for poem in poems for row in make_rows(poem, evaluator, assess)]
    jsonl_path = args.output_prefix.with_suffix(".jsonl")
    csv_path = args.output_prefix.with_suffix(".csv")
    audit_path = args.output_prefix.with_name(args.output_prefix.name + "_audit.json")
    jsonl_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    columns = ["candidate_id", "review_decision", "review_notes", "segment_kind", "category", "source_label", "text", "context_before", "context_after", "full_line_count", "block_index", "remainder_line_count", "url", "scr", "tcr", "rma", "is_valid_lucbat"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: (row["metrics"].get(column, "") if column in row["metrics"] else row.get(column, "")) for column in columns})
    audit = {
        "input": str(args.input),
        "source_poems": len(poems),
        "review_blocks": len(rows),
        "by_segment_kind": dict(Counter(row["segment_kind"] for row in rows)),
        "native_four_line": sum(row["segment_kind"] == "native_four_line" for row in rows),
        "derived_blocks": sum(row["segment_kind"] != "native_four_line" for row in rows),
        "fully_valid": sum(row["metrics"]["is_valid_lucbat"] for row in rows),
        "lexical_issue_blocks": sum(bool(row["lexical_issues"]) for row in rows),
        "policy": "review-only; never add to Tet4 SFT before reviewer confirms content and boundary",
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"jsonl": str(jsonl_path), "csv": str(csv_path), "audit": audit}, ensure_ascii=False))


if __name__ == "__main__":
    main()
