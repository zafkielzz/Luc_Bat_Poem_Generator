#!/usr/bin/env python3
"""So sánh reranker mặc định và lexical guard trên candidate pool đã sinh."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.evaluator import LucBatEvaluator
from engine.reranker import LucBatReranker
from scripts.generate_poem import load_cliches


def mean(rows, key):
    return round(sum(row["eval"][key] for row in rows) / len(rows), 3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    default = LucBatReranker(LucBatEvaluator(), load_cliches())
    guarded = LucBatReranker(LucBatEvaluator(), load_cliches(), lexical_guard=True)
    comparisons = []
    for source in args.candidates:
        for record in json.loads(source.read_text(encoding="utf-8")):
            poems = [item["poem"] for item in record["candidates"]]
            before = default.rerank(poems, record["metadata"])[0]
            after = guarded.rerank(poems, record["metadata"])[0]
            if before["poem"] != after["poem"]:
                comparisons.append({
                    "source": str(source), "prompt_id": record.get("prompt_id"),
                    "prompt": record["prompt"],
                    "before": {"poem": before["poem"], "eval": before["eval"]},
                    "after": {"poem": after["poem"], "eval": after["eval"],
                              "lexical": after["lexical"]},
                })
    selected_before = []
    selected_after = []
    for source in args.candidates:
        for record in json.loads(source.read_text(encoding="utf-8")):
            poems = [item["poem"] for item in record["candidates"]]
            selected_before.append(default.rerank(poems, record["metadata"])[0])
            selected_after.append(guarded.rerank(poems, record["metadata"])[0])
    result = {
        "version": "tet4-lexical-guard-offline-v1",
        "candidate_pools": len(selected_before),
        "selection_changes": len(comparisons),
        "before_mean": {key: mean(selected_before, key) for key in ("scr", "tcr", "rma", "overall")},
        "after_mean": {key: mean(selected_after, key) for key in ("scr", "tcr", "rma", "overall")},
        "changes": comparisons,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("candidate_pools", "selection_changes", "before_mean", "after_mean")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
