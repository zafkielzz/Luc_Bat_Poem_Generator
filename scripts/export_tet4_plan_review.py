#!/usr/bin/env python3
"""Export plan-assisted Tet4 pilot to a reviewer-friendly CSV."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "sft" / "tet4_plan_pilot_v1.jsonl"
OUTPUT = ROOT / "data" / "sft" / "tet4_plan_pilot_v1_review.csv"


def main() -> None:
    rows = [json.loads(line) for line in INPUT.read_text(encoding="utf-8").splitlines() if line]
    fields = ["pilot_id", "review_decision", "review_notes", "source_category", "source_label", "source_text", "recipient", "wish_intent", "keywords", "imagery", "tone", "line_1_role", "line_2_role", "line_3_role", "line_4_role", "source_url"]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            plan = row["plan"] or {}
            line_plan = plan.get("line_plan", [])
            writer.writerow({
                "pilot_id": row["pilot_id"], "review_decision": row["review_decision"], "review_notes": row["review_notes"],
                "source_category": row.get("source_category") or "", "source_label": row.get("source_label") or "", "source_text": row["source_text"],
                "recipient": plan.get("recipient", ""), "wish_intent": plan.get("wish_intent", ""),
                "keywords": ", ".join(plan.get("keywords", [])), "imagery": ", ".join(plan.get("imagery", [])), "tone": plan.get("tone", ""),
                "line_1_role": line_plan[0] if len(line_plan) > 0 else "", "line_2_role": line_plan[1] if len(line_plan) > 1 else "",
                "line_3_role": line_plan[2] if len(line_plan) > 2 else "", "line_4_role": line_plan[3] if len(line_plan) > 3 else "",
                "source_url": row.get("source_url") or "",
            })
    print(f"Exported {len(rows)} plans to {OUTPUT}")


if __name__ == "__main__":
    main()
