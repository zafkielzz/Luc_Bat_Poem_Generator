#!/usr/bin/env python3
"""Build the optional collocation asset from the quality FSoft corpus."""
import argparse, json
from pathlib import Path
from analyze_collocation import build_counts

def main():
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", type=Path, default=root / "data/sft/quality_fsoft_v1.jsonl")
    p.add_argument("--output", type=Path, default=root / "data/assets/collocation_fsoft_quality_v1.json")
    p.add_argument("--alpha", type=float, default=0.1)
    a = p.parse_args()
    uni, bi, tokens = build_counts(a.corpus)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps({"version":"collocation-fsoft-quality-v1","source":str(a.corpus),"alpha":a.alpha,"tokens":tokens,"unigram":dict(uni),"bigram":{f"{x}\t{y}":n for (x,y),n in bi.items()}},ensure_ascii=False),encoding="utf-8")
    print(f"unigrams={len(uni)} bigrams={len(bi)} output={a.output}")
if __name__ == "__main__": main()
