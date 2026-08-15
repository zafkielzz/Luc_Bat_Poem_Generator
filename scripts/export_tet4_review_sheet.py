#!/usr/bin/env python3
"""Xuất candidate Tet4 cũ thành CSV review/prompt; không sửa canonical JSONL."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "sft" / "archive" / "tet4_legacy_staging_v1" / "tet4_combined_staging_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "sft" / "tet4_gold_review_v2.csv"


def main() -> None:
    rows = [json.loads(line) for line in DEFAULT_INPUT.read_text(encoding="utf-8").splitlines() if line]
    columns = [
        "review_id", "review_priority", "decision_accept_reject",
        "content_label", "recipient", "wish_intent", "keywords_pipe",
        "prompt_draft", "prompt_ready_yes_no", "reviewer_notes", "poem",
        "source_id", "author", "domain", "url", "source_work_id",
        "scr", "tcr", "rma", "is_valid_lucbat",
    ]
    with DEFAULT_OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for index, record in enumerate(rows, start=1):
            metrics = record["metrics"]
            writer.writerow({
                "review_id": f"TET4-{index:03d}",
                "review_priority": "strict_valid" if metrics["is_valid_lucbat"] else "form_review_needed",
                "decision_accept_reject": "",
                "content_label": "",
                "recipient": "",
                "wish_intent": "",
                "keywords_pipe": "",
                "prompt_draft": "",
                "prompt_ready_yes_no": "",
                "reviewer_notes": "",
                "poem": record["text"],
                "source_id": record["source_id"],
                "author": record.get("author") or "",
                "domain": record.get("domain") or "",
                "url": record.get("url") or "",
                "source_work_id": record["source_work_id"],
                "scr": metrics["scr"],
                "tcr": metrics["tcr"],
                "rma": metrics["rma"],
                "is_valid_lucbat": metrics["is_valid_lucbat"],
            })
    print(f"Exported {len(rows)} rows to {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
