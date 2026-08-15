"""Fair ablation cho Stage 0 — Evaluation Freeze.

Mỗi prompt dùng cùng N ứng viên và cùng decoding config:
  1. Base no-thinking, no-engine: chọn candidate đầu tiên.
  2. Base + engine: chọn candidate đầu tiên từ cùng kích thước pool.
  3. Base + engine + reranker: rerank chính pool ở bước 2.

Nhờ vậy gain của N-best selection không bị lẫn với số candidate khác nhau. Raw
free-gen và toàn bộ candidate pool được lưu để audit.
"""
import argparse
import json
import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.evaluator import LucBatEvaluator
from engine.lucbat_engine import LucBatLogitsProcessor
from engine.reranker import LucBatReranker
from engine.vocab_assets import LucBatVocabAssets
from scripts.benchmark_batch import PROMPTS
from scripts.generate_poem import (
    ASSETS_DIR,
    MODEL_PATH,
    build_prompt,
    generate_batch,
    load_cliches,
    parse_metadata,
    set_seed,
)


META_HEADERS = ("bài thơ lục bát", "chủ đề", "số câu", "từ khoá", "vần gợi ý", "sáng tác")


def extract_poem(raw: str, max_lines: int = 8) -> str:
    """Chuẩn hoá free-gen output, chỉ làm defensive cleanup."""
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = raw.replace("<answer>", "").replace("</answer>", "")
    raw = raw.replace("<|im_start|>", "").replace("<|im_end|>", "")
    lines = []
    for line in raw.splitlines():
        clean = line.strip()
        if not clean:
            continue
        low = clean.lower()
        if any(low.startswith(header) or low == header for header in META_HEADERS):
            continue
        lines.append(clean)
        if len(lines) >= max_lines:
            break
    return "\n".join(lines)


def _aggregate(rows):
    if not rows:
        return {}
    metric_names = ("scr", "tcr", "exact_rma", "slant_rma", "rma", "overall")
    averages = {
        name: sum(row[name] for row in rows) / len(rows)
        for name in metric_names
    }
    return {
        **{name: round(value, 1) for name, value in averages.items()},
        "valid_n": sum(1 for row in rows if row["is_valid_lucbat"]),
        "n": len(rows),
    }


def _result_row(prompt, candidate_index, poem, evaluation, raw=None):
    row = {
        "prompt": prompt,
        "candidate_index": candidate_index,
        "poem": poem,
        **evaluation,
    }
    if raw is not None:
        row["raw"] = raw
    return row


def main():
    parser = argparse.ArgumentParser(
        description="Fair ablation: no-thinking free-gen vs engine vs N-best reranker"
    )
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--assets", default=ASSETS_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-samples", type=int, default=8)
    parser.add_argument("--max-prompts", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--out-dir", default=str(ROOT / "experiments"))
    args = parser.parse_args()

    if args.num_samples < 1:
        raise ValueError("num-samples phải >= 1")

    set_seed(args.seed)
    prompts = PROMPTS[:args.max_prompts] if args.max_prompts else PROMPTS
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print(
        f"FAIR ABLATION — {len(prompts)} prompt × N={args.num_samples} "
        f"(no-thinking, seed={args.seed})"
    )
    print("=" * 78)

    started = time.time()
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb,
        device_map={"": 0},
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    assets = LucBatVocabAssets.load(args.assets)
    evaluator = LucBatEvaluator()
    reranker = LucBatReranker(evaluator, load_cliches())

    configs = {"free_gen_first": [], "engine_first": [], "engine_rerank": []}
    candidate_pools = []

    for index, prompt in enumerate(prompts, 1):
        metadata = parse_metadata(prompt)
        target_lines = metadata["số câu"]
        stop_couplets = max(1, math.ceil(target_lines / 2))
        prompt_text = build_prompt(metadata)

        free_raws = generate_batch(
            model,
            tokenizer,
            None,
            prompt_text,
            args.num_samples,
            args.temperature,
            args.top_p,
            max_new_tokens=args.max_new_tokens,
            enable_thinking=False,
        )
        free_pool = [
            {
                "raw": raw,
                "poem": extract_poem(raw, max_lines=target_lines),
                "eval": evaluator.evaluate(
                    extract_poem(raw, max_lines=target_lines),
                    expected_num_lines=target_lines,
                ),
            }
            for raw in free_raws
        ]
        free_first = free_pool[0]

        processor = LucBatLogitsProcessor(
            assets,
            tone_penalty=1.5,
            rhyme_penalty=3.0,
            stop_after_couplets=stop_couplets,
            device="cuda",
        )
        engine_poems = generate_batch(
            model,
            tokenizer,
            processor,
            prompt_text,
            args.num_samples,
            args.temperature,
            args.top_p,
            max_new_tokens=args.max_new_tokens,
            enable_thinking=False,
        )
        engine_pool = [
            {"poem": poem, **reranker.score(poem, metadata)}
            for poem in engine_poems
        ]
        ranked_engine = sorted(
            engine_pool, key=lambda item: item["score"], reverse=True
        )
        engine_first = engine_pool[0]
        engine_best = ranked_engine[0]

        configs["free_gen_first"].append(
            _result_row(
                prompt,
                0,
                free_first["poem"],
                free_first["eval"],
                raw=free_first["raw"],
            )
        )
        configs["engine_first"].append(
            _result_row(prompt, 0, engine_first["poem"], engine_first["eval"])
        )
        configs["engine_rerank"].append(
            _result_row(
                prompt,
                engine_pool.index(engine_best),
                engine_best["poem"],
                engine_best["eval"],
            )
        )
        candidate_pools.append(
            {
                "prompt": prompt,
                "metadata": metadata,
                "free_gen": free_pool,
                "engine": engine_pool,
            }
        )

        print(
            f"[{index:>2}/{len(prompts)}] "
            f"free={free_first['eval']['overall']:5.1f}  "
            f"engine-first={engine_first['eval']['overall']:5.1f}  "
            f"rerank={engine_best['eval']['overall']:5.1f}"
        )

    table = {name: _aggregate(rows) for name, rows in configs.items()}
    print("\nCẤU HÌNH                SCR    TCR    RMA  overall  valid")
    for name in ("free_gen_first", "engine_first", "engine_rerank"):
        result = table[name]
        print(
            f"{name:<22} {result['scr']:>5.1f} {result['tcr']:>6.1f} "
            f"{result['rma']:>6.1f} {result['overall']:>8.1f} "
            f"{result['valid_n']:>3}/{result['n']}"
        )

    result = {
        "meta": {
            "script": "ablation_pipeline.py",
            "protocol_version": "stage0-evaluation-freeze-v1",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "model": args.model,
            "assets": args.assets,
            "seed": args.seed,
            "num_prompts": len(prompts),
            "num_samples": args.num_samples,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_new_tokens": args.max_new_tokens,
            "thinking_enabled": False,
            "selection_rules": {
                "free_gen_first": "candidate 0 from N candidates",
                "engine_first": "candidate 0 from the same-size engine pool",
                "engine_rerank": "reranker choice from engine_first pool",
            },
        },
        "table": table,
        "configs": configs,
        "candidate_pools": candidate_pools,
        "total_time_s": round(time.time() - started, 1),
    }
    out_path = out_dir / f"ablation_stage0_seed{args.seed}_n{len(prompts)}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
