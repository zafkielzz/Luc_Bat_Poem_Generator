"""
Tinh chỉnh trọng số reranker trên tập ứng viên đã lưu (CPU, không cần GPU).

Đọc `experiments/benchmark_candidates_seedN.json` (sinh bởi `benchmark_batch.py`, seed cố định),
thử từng bộ weight, đo cho từng prompt:
  - top1_agree: reranker chọn đúng ứng viên có overall cao nhất không
  - aggregate:  overall trung bình của bài được chọn (best-of-N)
  - corr:       Pearson giữa score rerank và overall evaluator

Chọn bộ weight cân bằng: top1_agree cao (chất lượng vần phải thắng) NHƯNG vẫn giữ
keyword như tiebreaker (bài lạc đề dù hợp vần không nên thắng bài đúng chủ đề chênh
vài điểm).

Chạy: python scripts/tune_reranker_weights.py
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.evaluator import LucBatEvaluator
from engine.reranker import LucBatReranker
from scripts.generate_poem import load_cliches

WEIGHT_SETS = [
    # (name, weights)
    ("OLD (0.35/0.20) - regression", {"evaluator": 0.35, "diversity": 0.20, "cliche": 0.15,
                                      "keyword": 0.20, "length": 0.10}),
    ("NEW 0.50/0.12 (đang dùng)", {"evaluator": 0.50, "diversity": 0.15, "cliche": 0.15,
                                   "keyword": 0.12, "length": 0.08}),
    ("0.55/0.10", {"evaluator": 0.55, "diversity": 0.14, "cliche": 0.13,
                   "keyword": 0.10, "length": 0.08}),
    ("0.60/0.10", {"evaluator": 0.60, "diversity": 0.13, "cliche": 0.12,
                   "keyword": 0.10, "length": 0.05}),
    ("0.65/0.08", {"evaluator": 0.65, "diversity": 0.12, "cliche": 0.11,
                   "keyword": 0.08, "length": 0.04}),
    ("0.70/0.06", {"evaluator": 0.70, "diversity": 0.10, "cliche": 0.10,
                   "keyword": 0.06, "length": 0.04}),
    ("0.75/0.12cl/0.05kw", {"evaluator": 0.75, "diversity": 0.05, "cliche": 0.12,
                            "keyword": 0.05, "length": 0.03}),
    ("0.75/0.08dv/0.10cl", {"evaluator": 0.75, "diversity": 0.08, "cliche": 0.10,
                            "keyword": 0.05, "length": 0.02}),
    ("0.78/0.06dv/0.10cl", {"evaluator": 0.78, "diversity": 0.06, "cliche": 0.10,
                            "keyword": 0.04, "length": 0.02}),
    ("0.80/0.05dv/0.10cl", {"evaluator": 0.80, "diversity": 0.05, "cliche": 0.10,
                            "keyword": 0.03, "length": 0.02}),
    ("0.80/0.10cl/0.04kw", {"evaluator": 0.80, "diversity": 0.04, "cliche": 0.10,
                            "keyword": 0.04, "length": 0.02}),
    ("0.85/0.07cl/0.03kw", {"evaluator": 0.85, "diversity": 0.03, "cliche": 0.07,
                            "keyword": 0.03, "length": 0.02}),
    ("0.90/0.02 (gần thuần evaluator)", {"evaluator": 0.90, "diversity": 0.04, "cliche": 0.02,
                                          "keyword": 0.02, "length": 0.02}),
]


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return 0.0
    return cov / (vx * vy) ** 0.5


def main():
    ap = argparse.ArgumentParser(description="Tinh chỉnh weight reranker trên dump benchmark")
    ap.add_argument("--dump", default=str(ROOT / "experiments" / "benchmark_candidates_seed42.json"))
    args = ap.parse_args()

    dump = json.loads(Path(args.dump).read_text(encoding="utf-8"))
    evaluator = LucBatEvaluator()
    cliches = load_cliches()
    print(f"Loaded {len(dump)} prompts từ {args.dump}\n")

    print(f"{'weight set':<26} {'top1_ok':>7} {'agg_overall':>11} {'corr':>5}   per-prompt top1_ok")
    for name, w in WEIGHT_SETS:
        rk = LucBatReranker(evaluator, cliches, weights=w)
        top1s, overalls, corrs = [], [], []
        per = ""
        for pr in dump:
            ranked = rk.rerank([c["poem"] for c in pr["candidates"]], pr["metadata"])
            best = ranked[0]
            best_overall = max(c["eval"]["overall"] for c in pr["candidates"])
            ok = 1.0 if abs(best["eval"]["overall"] - best_overall) < 1e-9 else 0.0
            top1s.append(ok)
            overalls.append(best["eval"]["overall"])
            corrs.append(pearson([r["score"] for r in ranked],
                                 [r["eval"]["overall"] for r in ranked]))
            per += "✓" if ok else "✗"
        n = len(top1s)
        print(f"{name:<26} {sum(top1s)/n*100:>6.0f}% {sum(overalls)/n:>11.1f} "
              f"{sum(corrs)/n:>5.2f}   {per}")


if __name__ == "__main__":
    main()
