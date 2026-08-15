#!/usr/bin/env python3
"""Giải mã phiếu paired blind A/B/tie sau khi người chấm hoàn tất."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def analyze(ratings_path: Path, key_path: Path) -> dict:
    with ratings_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    key = json.loads(key_path.read_text(encoding="utf-8"))
    mapping = {item["pair_id"]: item for item in key["items"]}
    if {row.get("pair_id") for row in rows} != set(mapping):
        raise ValueError("pair_id trong ratings không khớp blind key")
    counts = Counter()
    decoded = []
    for row in rows:
        preference = row.get("preference", "").strip().upper()
        if preference not in {"A", "B", "TIE"}:
            raise ValueError(f"{row['pair_id']}: preference phải là A, B hoặc tie")
        item = mapping[row["pair_id"]]
        winner = "tie" if preference == "TIE" else item[preference]
        counts[winner] += 1
        decoded.append({"pair_id": row["pair_id"], "prompt_id": item["prompt_id"],
                        "preference": preference, "winner": winner,
                        "strength": row.get("strength", "").strip()})
    return {"version": key.get("version"), "prompt_count": len(rows),
            "counts": dict(counts), "items": decoded}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings", type=Path, required=True)
    parser.add_argument("--blind-key", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.ratings, args.blind_key)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
