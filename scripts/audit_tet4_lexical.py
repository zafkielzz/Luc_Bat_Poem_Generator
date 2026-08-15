#!/usr/bin/env python3
"""Audit lexical cho candidate Tet4 đã lưu; không thay đổi thứ tự reranker."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.lexical_guard import assess


def audit(paths):
    findings = []
    by_type = Counter()
    total = 0
    for path in paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        for record in payload:
            keywords = record.get("metadata", {}).get("từ khoá") or record.get("metadata", {}).get("keywords") or []
            for candidate_index, candidate in enumerate(record["candidates"], 1):
                total += 1
                result = assess(candidate["poem"], keywords)
                if not result["hard_fail"]:
                    continue
                for issue in result["issues"]:
                    by_type[issue["type"]] += 1
                findings.append({
                    "source": str(path), "prompt_id": record.get("prompt_id"),
                    "prompt": record["prompt"], "candidate_index": candidate_index,
                    "poem": candidate["poem"], "keywords": keywords,
                    "issues": result["issues"],
                })
    return {"version": "tet4-lexical-audit-v1", "total_candidates": total,
            "failed_candidates": len(findings), "issue_counts": dict(by_type),
            "findings": findings}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.candidates)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("total_candidates", "failed_candidates", "issue_counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
