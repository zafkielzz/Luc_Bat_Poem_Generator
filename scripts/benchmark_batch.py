"""
Benchmark batch (Task 5.1): chạy N prompt trên Qwen3-8B chưa finetune, tổng hợp
SCR/TCR/RMA cho baseline sạch — số aggregate đáng tin (không phải single-run may rủi).

Nạp model MỘT lần, lặp qua từng prompt:
  parse_metadata -> build_prompt (structured, no CoT) -> generate 8 ứng viên
  -> LucBatEvaluator.evaluate -> LucBatReranker.rerank

Đầu ra:
  - Bảng per-prompt: best-of-8 (SCR/TCR/RMA/overall/valid) + top1_agree
    (reranker có chọn đúng ứng viên overall cao nhất không).
  - Aggregate: trung bình SCR/TCR/RMA/overall, % valid.
  - top1_agree + correlation score~overall dùng để KIỂM CHỨNG weight của reranker
    (0.80/0.05/0.10/0.03/0.02 — tune bằng `tune_reranker_weights.py` trên dump ứng viên).
  - Lưu kết quả + ứng viên thành JSON có cấu trúc vào `experiments/` (reproducibility,
    khuyến nghị A4/expert review).

Chạy (env capstone, GPU):
    python scripts/benchmark_batch.py --num-samples 8
"""
import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.evaluator import LucBatEvaluator
from engine.lucbat_engine import LucBatLogitsProcessor
from engine.reranker import DEFAULT_WEIGHTS, LucBatReranker
from engine.tet4_protocol import PROTOCOL_VERSION, normalize_metadata, validate_manifest
from engine.vocab_assets import LucBatVocabAssets
from scripts.generate_poem import (
    MODEL_PATH, ASSETS_DIR, CLICHES_PATH, load_cliches,
    parse_metadata, build_prompt, build_messages, generate_batch, set_seed,
)

PROMPTS = [
    # Xuân / Tết
    "viết bài thơ lục bát 4 câu về mùa xuân",
    "viết bài thơ lục bát 4 câu chúc tết ông bà",
    "viết bài thơ lục bát 4 câu về hoa mai ngày tết",
    "viết bài thơ lục bát 4 câu về tết sum vầy gia đình",
    "viết bài thơ lục bát 4 câu về mùa xuân nơi bản làng",
    # Tình cảm gia đình
    "viết bài thơ lục bát 4 câu về tình mẹ",
    "viết bài thơ lục bát 4 câu về mái ấm gia đình",
    "viết bài thơ lục bát 4 câu về ơn cha nghĩa mẹ",
    "viết bài thơ lục bát 4 câu về sự hiếu thảo của con",
    "viết bài thơ lục bát 4 câu về lễ vu lan báo hiếu",
    # Quê hương / đồng quê
    "viết bài thơ lục bát 4 câu về quê hương",
    "viết bài thơ lục bát 4 câu tả cảnh đồng quê",
    "viết bài thơ lục bát 4 câu về dòng sông quê",
    "viết bài thơ lục bát 4 câu về lũy tre đầu làng",
    "viết bài thơ lục bát 4 câu về con đò sông nước",
    "viết bài thơ lục bát 4 câu về cánh đồng lúa chín",
    "viết bài thơ lục bát 4 câu về mùa gặt bội thu",
    "viết bài thơ lục bát 4 câu về cây đa giếng nước",
    "viết bài thơ lục bát 4 câu về phiên chợ quê buổi sớm",
    "viết bài thơ lục bát 4 câu về ruộng bậc thang mùa nước đổ",
    # Cảnh vật / bốn mùa
    "viết bài thơ lục bát 4 câu về mùa thu",
    "viết bài thơ lục bát 4 câu về mùa hè",
    "viết bài thơ lục bát 4 câu về mùa đông giá rét",
    "viết bài thơ lục bát 4 câu về cơn mưa đầu mùa",
    "viết bài thơ lục bát 4 câu về hoa sen mùa hạ",
    "viết bài thơ lục bát 4 câu về hoa phượng sân trường",
    "viết bài thơ lục bát 4 câu về trăng rằm tháng tám",
    "viết bài thơ lục bát 4 câu về đêm trăng thanh bình",
    "viết bài thơ lục bát 4 câu về ngọn núi và rừng xanh",
    "viết bài thơ lục bát 4 câu về biển đảo",
    # Đất nước / lịch sử
    "viết bài thơ lục bát 4 câu về Bác Hồ kính yêu",
    "viết bài thơ lục bát 4 câu về biên cương tổ quốc",
    "viết bài thơ lục bát 4 câu về Trường Sa quê hương",
    "viết bài thơ lục bát 4 câu về đền Hùng lịch sử",
    "viết bài thơ lục bát 4 câu về sông nước miền tây",
    "viết bài thơ lục bát 4 câu về cao nguyên đá hùng vĩ",
    # Trường học / bạn bè
    "viết bài thơ lục bát 4 câu nhớ trường xưa",
    "viết bài thơ lục bát 4 câu về ngày khai trường",
    "viết bài thơ lục bát 4 câu về ơn thầy cô",
    "viết bài thơ lục bát 4 câu về tình bạn thân",
    "viết bài thơ lục bát 4 câu về mùa thi và bạn bè",
    "viết bài thơ lục bát 4 câu về ước mơ tuổi học trò",
    # Đời sống / tâm tình
    "viết bài thơ lục bát 4 câu chúc mừng sinh nhật bạn",
    "viết bài thơ lục bát 4 câu về tình yêu đôi lứa",
    "viết bài thơ lục bát 4 câu về nỗi nhớ quê nhà",
    "viết bài thơ lục bát 4 câu về tuổi trẻ và khát vọng",
    "viết bài thơ lục bát 4 câu về hy vọng ngày mới",
    "viết bài thơ lục bát 4 câu về giấc mơ đêm hè",
    "viết bài thơ lục bát 4 câu về làng nghề truyền thống",
    "viết bài thơ lục bát 4 câu về phiên chợ nổi miền tây",
]


TEST_MANIFEST_PATH = ROOT / "data" / "evaluation" / "test_prompts_v1.json"


def load_prompt_records(prompt_manifest=None):
    """Load fresh held-out prompts or return the legacy development set."""
    if prompt_manifest is None:
        return (
            [{"id": f"D{i:02d}", "prompt": prompt} for i, prompt in enumerate(PROMPTS, 1)],
            {"version": "legacy-dev", "split": "development", "path": None},
        )
    path = Path(prompt_manifest)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") == PROTOCOL_VERSION:
        prompts = validate_manifest(data)
    else:
        prompts = data.get("prompts", [])
        if not prompts or any(not item.get("prompt") for item in prompts):
            raise ValueError(f"Prompt manifest không hợp lệ: {path}")
    return prompts, {
        "version": data.get("version", "unknown"),
        "split": data.get("split", "test"),
        "path": str(path),
    }


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
    ap = argparse.ArgumentParser(description="Benchmark batch baseline Lục Bát")
    ap.add_argument("--num-samples", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=0.9)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--model", default=MODEL_PATH)
    ap.add_argument("--adapter", default=None, help="Đường dẫn LoRA adapter; mặc định là baseline")
    ap.add_argument("--assets", default=ASSETS_DIR)
    ap.add_argument("--seed", type=int, default=42, help="Seed RNG để tái lập kết quả")
    ap.add_argument("--out-dir", default=str(ROOT / "experiments"),
                    help="Thư mục lưu JSON kết quả + ứng viên")
    ap.add_argument("--save-candidates", default=None,
                    help="Đè đường dẫn lưu ứng viên (mặc định: <out-dir>/benchmark_candidates_seedN.json)")
    ap.add_argument(
        "--prompt-manifest",
        default=None,
        help="JSON manifest prompt holdout; mặc định dùng PROMPTS development lịch sử",
    )
    ap.add_argument("--max-prompts", type=int, default=None)
    ap.add_argument("--lexical-guard", action="store_true",
                    help="Loại candidate có lỗi từ cụt chắc chắn, ví dụ 'tri â'")
    ap.add_argument("--soft-form", action="store_true",
                    help="Chế độ chẩn đoán cũ: chỉ phạt thanh/vần; mặc định ép luật cứng và từ chối bài không đạt.")
    ap.add_argument("--strict-retries", type=int, default=1,
                    help="Số batch sinh lại khi 8 ứng viên đầu chưa có bài đúng luật; chỉ dùng ở strict form.")
    args = ap.parse_args()

    set_seed(args.seed)
    prompt_records, prompt_protocol = load_prompt_records(args.prompt_manifest)
    if args.max_prompts is not None:
        prompt_records = prompt_records[:args.max_prompts]
    if not prompt_records:
        raise ValueError("Không có prompt để benchmark")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cand_path = Path(args.save_candidates) if args.save_candidates else \
        out_dir / f"benchmark_candidates_seed{args.seed}.json"

    print("=" * 78)
    print(f"🧪 BENCHMARK BATCH — {len(prompt_records)} prompt × {args.num_samples} ứng viên "
          f"(Qwen3-8B chưa finetune, lexicon sạch, seed={args.seed})")
    print("=" * 78)

    t0 = time.time()
    print("\n[1/3] Nạp mô hình 4-bit + assets (một lần)...")
    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, quantization_config=bnb, device_map={"": 0},
        trust_remote_code=True, torch_dtype=torch.bfloat16)

    if args.adapter:
        adapter_path = Path(args.adapter)
        if not (adapter_path / "adapter_config.json").is_file():
            raise FileNotFoundError(f"Không tìm thấy adapter_config.json: {adapter_path}")
        model = PeftModel.from_pretrained(model, str(adapter_path))
        print(f"   ✓ Đã nạp LoRA adapter: {adapter_path}")
    model.eval()
    assets = LucBatVocabAssets.load(args.assets)
    print(f"   ✓ Model + assets sẵn sàng ({time.time()-t0:.0f}s)")

    evaluator = LucBatEvaluator()
    reranker = LucBatReranker(evaluator, load_cliches(), lexical_guard=args.lexical_guard)
    dump = []  # lưu ứng viên để tinh chỉnh weight CPU
    rows = []
    t1 = time.time()
    for pi, prompt_record in enumerate(prompt_records, 1):
        prompt = prompt_record["prompt"]
        metadata = (prompt_record["metadata"]
                    if prompt_record.get("metadata") else parse_metadata(prompt))
        stop_couplets = max(1, math.ceil(metadata["số câu"] / 2))
        proc = LucBatLogitsProcessor(
            assets, tone_penalty=1.5, rhyme_penalty=3.0,
            stop_after_couplets=stop_couplets, device="cuda",
            strict_tone=not args.soft_form, strict_rhyme=not args.soft_form)

        poems = generate_batch(model, tokenizer, proc, build_prompt(metadata),
                               args.num_samples, args.temperature, args.top_p)
        ranked_all = reranker.rerank(poems, metadata)
        eligible = [item for item in ranked_all if item["eval"]["is_valid_lucbat"]
                    and not item.get("lexical", {}).get("hard_fail", False)]
        attempts = 1
        while not args.soft_form and not eligible and attempts <= args.strict_retries:
            poems.extend(generate_batch(model, tokenizer, proc, build_prompt(metadata),
                                        args.num_samples, args.temperature, args.top_p))
            attempts += 1
            ranked_all = reranker.rerank(poems, metadata)
            eligible = [item for item in ranked_all if item["eval"]["is_valid_lucbat"]
                        and not item.get("lexical", {}).get("hard_fail", False)]
        ranked = ranked_all if args.soft_form else eligible
        ordered = ranked + [item for item in ranked_all if item not in ranked]
        dump.append({
            "prompt": prompt, "metadata": metadata, "prompt_id": prompt_record.get("id"),
            "strict_form": not args.soft_form, "attempts": attempts,
            "strict_relaxations": proc.strict_relaxations,
            "output_available": bool(ranked),
            "candidates": [{"poem": item["poem"], "eval": item["eval"],
                            "eligible_for_output": item in eligible} for item in ordered],
        })

        best = ranked[0] if ranked else ranked_all[0]
        e = best["eval"]
        best_overall = max(r["eval"]["overall"] for r in ranked_all)
        top1_agree = 1.0 if abs(e["overall"] - best_overall) < 1e-9 else 0.0
        corr = pearson([r["score"] for r in ranked_all],
                       [r["eval"]["overall"] for r in ranked_all])

        rows.append({"prompt": prompt, "ev": e, "top1_agree": top1_agree, "corr": corr,
                     "output_available": bool(ranked),
                     "first_line": best["poem"].split("\n")[0][:40]})
        print(f"  [{pi:>2}/{len(prompt_records)}] {prompt[:34]:<34} "
              f"SCR={e['scr']:.0f} TCR={e['tcr']:.0f} RMA={e['rma']:.0f} "
              f"overall={e['overall']:.1f} {('✓' if ranked else 'REJECT')}")

    print(f"\n[2/3] Thời gian gen {len(prompt_records)} prompt: {time.time()-t1:.1f}s")

    # Lưu ứng viên để tinh chỉnh weight reranker trong CPU (không cần chạy lại GPU).
    Path(cand_path).write_text(
        json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"💾 Đã lưu {len(dump)} prompt × {args.num_samples} ứng viên: {cand_path}")

    print("\n" + "-" * 78)
    print("📋 BẢNG PER-PROMPT (best-of-N, sau rerank)")
    print("-" * 78)
    print(f"{'#':>2}  {'SCR':>5} {'TCR':>5} {'RMA':>5} {'overall':>8} {'valid':>5} "
          f"{'top1_ok':>7} {'corr':>5}  prompt / dòng đầu")
    for i, r in enumerate(rows, 1):
        e = r["ev"]
        print(f"{i:>2}  {e['scr']:>5.0f} {e['tcr']:>5.0f} {e['rma']:>5.0f} "
              f"{e['overall']:>8.1f} {('✓' if e['is_valid_lucbat'] else '✗'):>5} "
              f"{('OK' if r['top1_agree'] else 'X'):>7} {r['corr']:>5.2f}  "
              f"{r['prompt'][:24]} / {r['first_line']}")

    n = len(rows)
    avg = {
        k: sum(r["ev"][k] for r in rows) / n
        for k in ("scr", "tcr", "exact_rma", "slant_rma", "rma", "overall")
    }
    valid_n = sum(1 for r in rows if r["output_available"])
    rejected_n = n - valid_n
    top1_ok = sum(r["top1_agree"] for r in rows) / n
    avg_corr = sum(r["corr"] for r in rows) / n

    print("\n" + "=" * 78)
    print(f"📊 AGGREGATE ({n} bài best-of-{args.num_samples})")
    print(f"   SCR   = {avg['scr']:.1f}   (engine hard-constraint bảo đảm 100)")
    print(f"   TCR   = {avg['tcr']:.1f}")
    print(f"   exact RMA = {avg['exact_rma']:.1f}")
    print(f"   slant RMA = {avg['slant_rma']:.1f}")
    print(f"   combined RMA = {avg['rma']:.1f}")
    print(f"   overall = {avg['overall']:.1f}")
    print(f"   output accepted (SCR=100, TCR=100, RMA=100): {valid_n}/{n}; rejected: {rejected_n}")
    print(f"   top1_agree (reranker chọn đúng ứng viên overall cao nhất): {top1_ok:.0%}")
    print(f"   corr trung bình (score rerank ~ overall evaluator): {avg_corr:.2f}")
    print(f"   Tổng thời gian: {time.time()-t0:.1f}s")

    # Lưu kết quả JSON có cấu trúc (reproducibility — experiments/, khuyến nghị A4).
    result = {
        "meta": {
            "script": "benchmark_batch.py",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "model": args.model,
            "adapter": args.adapter,
            "seed": args.seed,
            "num_prompts": len(prompt_records),
            "prompt_protocol": prompt_protocol,
            "num_samples": args.num_samples,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "engine": {"tone_penalty": 1.5, "rhyme_penalty": 3.0, "strict_form": not args.soft_form,
                       "strict_retries": args.strict_retries},
            "reranker_weights": DEFAULT_WEIGHTS,
            "lexical_guard": args.lexical_guard,
        },
        "aggregate": {
            "scr": round(avg["scr"], 1), "tcr": round(avg["tcr"], 1),
            "exact_rma": round(avg["exact_rma"], 1),
            "slant_rma": round(avg["slant_rma"], 1),
            "rma": round(avg["rma"], 1), "overall": round(avg["overall"], 1),
            "valid_n": valid_n, "rejected_n": rejected_n, "top1_agree_pct": round(top1_ok, 3),
            "avg_corr": round(avg_corr, 3), "total_time_s": round(time.time() - t0, 1),
        },
        "rows": [
            {"prompt": r["prompt"], "scr": r["ev"]["scr"], "tcr": r["ev"]["tcr"],
             "exact_rma": r["ev"]["exact_rma"], "slant_rma": r["ev"]["slant_rma"],
             "rma": r["ev"]["rma"], "overall": r["ev"]["overall"],
             "valid": r["output_available"], "top1_agree": r["top1_agree"],
             "corr": round(r["corr"], 3), "first_line": r["first_line"]}
            for r in rows
        ],
    }
    result_path = out_dir / f"benchmark_seed{args.seed}_n{len(prompt_records)}.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"💾 Đã lưu kết quả JSON: {result_path}")


if __name__ == "__main__":
    main()
