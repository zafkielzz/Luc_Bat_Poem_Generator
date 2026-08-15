"""
Sinh thơ Lục Bát end-to-end — baseline trên Qwen3-8B chưa finetune.

Pipeline:
  1. Nạp Qwen3-8B 4-bit (BitsAndBytes nf4, ~5GB VRAM).
  2. build_prompt(metadata): prompt có cấu trúc, KHÔNG CoT, KHÔNG <think>.
  3. generate(8 ứng viên) qua LucBatLogitsProcessor (hard 6/8 + newline, soft -λ
     thanh/vần, trie subword, stop sau đủ số cặp câu).
  4. LucBatEvaluator.evaluate từng bài -> LucBatReranker.rerank -> in best-of-8.

Chạy (trong env `capstone`, GPU):
    python scripts/generate_poem.py "viết bài lục bát 4 câu về mùa xuân"
    python scripts/generate_poem.py --num-samples 8 --temperature 0.9 "chúc tết bà 6 câu"
"""
import argparse
import math
import random
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.evaluator import LucBatEvaluator
from engine.lucbat_engine import LucBatLogitsProcessor
from engine.reranker import LucBatReranker
from engine.vocab_assets import LucBatVocabAssets

MODEL_PATH = "/media/zafkiel/WORK_SPACE2/models/Qwen3-8B"
ASSETS_DIR = str(ROOT / "data" / "assets")
CLICHES_PATH = ROOT / "data" / "cliches.txt"

# Từ dừng tiếng Việt cho việc rút từ khoá từ prompt (không phải lexicon đầy đủ).
STOPWORDS = {
    "viết", "bài", "thơ", "lục", "bát", "về", "một", "của", "để", "cho",
    "và", "có", "là", "trong", "trên", "những", "các", "này", "đó", "như",
    "bạn", "tôi", "em", "anh", "câu", "dòng", "đi", "với", "ở", "được",
    "vần",
}


def load_cliches(path=CLICHES_PATH) -> list:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")]


def set_seed(seed: int):
    """Cố định seed → thí nghiệm tái lập được (reproducibility, khuyến nghị A4/expert review).

    Gọi TRƯỚC khi generate; `model.generate(do_sample=True)` dùng global RNG của torch
    nên cùng seed + cùng tham số → cùng dãy ứng viên (trên cùng phần cứng).
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


# ------------------------------------------------------------------ metadata
def parse_metadata(prompt: str) -> dict:
    """Rút metadata cấu trúc từ prompt tự do: số câu, vần gợi ý, từ khoá, chủ đề."""
    low = prompt.lower()
    num_lines = 4
    m = re.search(r"(\d+)\s*(?:câu|dòng)", low)
    if m:
        num_lines = int(m.group(1))
    rhyme = None
    m = re.search(r"vần\s+([a-zà-ỹ]{1,4})\b", low)
    if m:
        rhyme = m.group(1)
    keywords = [w for w in re.split(r"[^a-zà-ỹ]+", low)
                if w and w not in STOPWORDS][:5]
    return {
        "chủ đề": prompt.strip(),
        "số câu": num_lines,
        "từ khoá": keywords,
        "vần gợi ý": rhyme,
    }


def build_prompt(metadata: dict) -> str:
    """Prompt có cấu trúc — đầu vào trực tiếp cho SFT sau này (không CoT)."""
    parts = ["BÀI THƠ LỤC BÁT"]
    if metadata.get("người nhận"):
        parts.append(f"Người nhận lời chúc: {metadata['người nhận']}")
    if metadata.get("ý chúc"):
        parts.append(f"Ý chúc: {metadata['ý chúc']}")
    if metadata.get("chủ đề"):
        parts.append(f"Chủ đề: {metadata['chủ đề']}")
    parts.append(f"Số câu: {metadata['số câu']} (mỗi câu Lục 6 âm tiết, Bát 8 âm tiết)")
    if metadata.get("từ khoá"):
        parts.append(f"Từ khoá: {', '.join(metadata['từ khoá'])}")
    if metadata.get("vần gợi ý"):
        parts.append(f"Vần gợi ý: {metadata['vần gợi ý']}")
    parts.append("Sáng tác trực tiếp bài thơ, không giải thích, không suy luận.")
    return "\n".join(parts)


# ------------------------------------------------------------------ generation
def build_messages(prompt_text: str):
    system = (
        "Bạn là một thi sĩ Việt Nam am hiểu thơ Lục Bát. "
        "Sáng tác trực tiếp bài thơ Lục Bát đúng luật: dòng 6 âm tiết, dòng 8 âm tiết, "
        "vần lưng (tiếng 6 câu Lục với tiếng 6 câu Bát) và vần chân (tiếng 8 câu Bát với "
        "tiếng 6 câu Lục kế tiếp). Không dùng thẻ <think>, không giải thích."
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": prompt_text}]


def render_chat_prompt(tokenizer, messages, enable_thinking: bool = False):
    """Render chat prompt và truyền cờ no-thinking cho tokenizer Qwen3."""
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )
    newline = chr(10)
    return (
        "<|im_start|>system" + newline + messages[0]["content"] + "<|im_end|>" + newline
        + "<|im_start|>user" + newline + messages[1]["content"] + "<|im_end|>" + newline
        + "<|im_start|>assistant" + newline
    )


def generate_batch(model, tokenizer, proc, prompt_text, num_samples, temperature, top_p,
                   max_new_tokens=300, enable_thinking: bool = False):
    """proc=None → free-gen KHÔNG engine (dùng cho ablation: so sánh +engine vs -engine)."""
    messages = build_messages(prompt_text)
    prompt_text_full = render_chat_prompt(
        tokenizer, messages, enable_thinking=enable_thinking
    )
    inputs = tokenizer(prompt_text_full, return_tensors="pt").to("cuda")
    if proc is not None:
        proc.reset()  # rows mới cho mỗi batch

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            logits_processor=[proc] if proc is not None else None,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=1.1,
            num_return_sequences=num_samples,
            max_new_tokens=max_new_tokens,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.eos_token_id,
        )

    prompt_len = inputs.input_ids.shape[1]
    poems = []
    for i in range(num_samples):
        raw = tokenizer.decode(outputs[i][prompt_len:], skip_special_tokens=True).strip()
        poems.append(raw)
    return poems


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Sinh thơ Lục Bát baseline (Qwen3-8B + engine + reranker)")
    ap.add_argument("prompt", nargs="?", default="viết bài lục bát 4 câu về mùa xuân")
    ap.add_argument("--model", default=MODEL_PATH)
    ap.add_argument("--assets", default=ASSETS_DIR)
    ap.add_argument("--num-samples", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=0.9)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--tone-penalty", type=float, default=1.5)
    ap.add_argument("--rhyme-penalty", type=float, default=3.0)
    ap.add_argument("--lexical-guard", action="store_true",
                    help="Loại candidate có lỗi từ cụt chắc chắn, ví dụ 'tri â'")
    ap.add_argument("--soft-form", action="store_true",
                    help="Chế độ chẩn đoán cũ; mặc định chỉ xuất bài có luật bằng–trắc và vần đạt tuyệt đối.")
    ap.add_argument("--seed", type=int, default=42, help="Seed RNG để tái lập kết quả")
    args = ap.parse_args()

    set_seed(args.seed)
    print(f"🔒 seed={args.seed} (để tái lập kết quả, cùng seed + tham số → cùng dãy ứng viên)")

    metadata = parse_metadata(args.prompt)
    num_lines = metadata["số câu"]
    stop_couplets = max(1, math.ceil(num_lines / 2))  # mỗi cặp Lục-Bát = 2 dòng

    print("=" * 60)
    print("🚀 SINH THƠ LỤC BÁT — BASELINE Qwen3-8B (no CoT, logits engine + reranker)")
    print(f"   Prompt : {args.prompt}")
    print(f"   Số câu  : {num_lines} (stop_after_couplets={stop_couplets})")
    print(f"   Keyword : {metadata['từ khoá']}")
    print("=" * 60)

    t0 = time.time()
    print("\n[1/3] Nạp mô hình 4-bit + assets...")
    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, quantization_config=bnb, device_map={"": 0},
        trust_remote_code=True, torch_dtype=torch.bfloat16)
    assets = LucBatVocabAssets.load(args.assets)
    proc = LucBatLogitsProcessor(
        assets, tone_penalty=args.tone_penalty, rhyme_penalty=args.rhyme_penalty,
        stop_after_couplets=stop_couplets, device="cuda",
        strict_tone=not args.soft_form, strict_rhyme=not args.soft_form)
    print(f"   ✓ Model + assets sẵn sàng ({time.time()-t0:.0f}s)")

    prompt_text = build_prompt(metadata)
    print(f"\n[2/3] Prompt (structured, no CoT):\n{prompt_text}\n")

    print("[3/3] Sinh %d ứng viên, đánh giá + rerank..." % args.num_samples)
    t1 = time.time()
    poems = generate_batch(model, tokenizer, proc, prompt_text,
                           args.num_samples, args.temperature, args.top_p)
    gen_s = time.time() - t1

    evaluator = LucBatEvaluator()
    reranker = LucBatReranker(evaluator, load_cliches(), lexical_guard=args.lexical_guard)
    ranked_all = reranker.rerank(poems, metadata)
    eligible = [r for r in ranked_all if r["eval"]["is_valid_lucbat"]
                and not r.get("lexical", {}).get("hard_fail", False)]
    ranked = ranked_all if args.soft_form else eligible
    if not ranked:
        print("\nREJECT: Không có ứng viên qua SCR=100, TCR=100, RMA=100; không xuất thơ.")
        return

    print("\n" + "=" * 60)
    print("🏆 BÀI THƠ HAY NHẤT")
    print("=" * 60)
    best = ranked[0]
    print(best["poem"])
    e = best["eval"]
    print(f"\n   SCR={e['scr']:.0f}  TCR={e['tcr']:.0f}  RMA={e['rma']:.0f}  "
          f"overall={e['overall']:.1f}  valid={'✓' if e['is_valid_lucbat'] else '✗'}")

    print("\n" + "-" * 60)
    print(f"📊 XẾP HẠNG {len(ranked)} ỨNG VIÊN (sau rerank)")
    print("-" * 60)
    print(f"{'#':>2}  {'SCR':>5} {'TCR':>5} {'RMA':>5} {'overall':>8} {'score':>6}  dòng đầu")
    for i, r in enumerate(ranked, 1):
        ev = r["eval"]
        first_line = r["poem"].split("\n")[0][:40]
        print(f"{i:>2}  {ev['scr']:>5.0f} {ev['tcr']:>5.0f} {ev['rma']:>5.0f} "
              f"{ev['overall']:>8.1f} {r['score']:>6.3f}  {first_line}")

    valid_n = sum(1 for r in ranked if r["eval"]["is_valid_lucbat"])
    avg_overall = sum(r["eval"]["overall"] for r in ranked) / len(ranked)
    print(f"\n   Đạt chuẩn (SCR=100, TCR=100, RMA=100): {valid_n}/{len(ranked)}")
    print(f"   Overall trung bình: {avg_overall:.1f}   Thời gian gen: {gen_s:.1f}s")

    # Lưu ra file để làm baseline sau này
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    (out / "baseline_best.txt").write_text(
        f"{args.prompt}\n\n{best['poem']}\n\n"
        f"SCR={e['scr']:.0f} TCR={e['tcr']:.0f} RMA={e['rma']:.0f} overall={e['overall']:.1f}\n",
        encoding="utf-8")
    print(f"\n💾 Đã lưu bài hay nhất vào outputs/baseline_best.txt")


if __name__ == "__main__":
    main()
