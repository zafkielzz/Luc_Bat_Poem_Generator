#!/usr/bin/env python3
"""Generate reviewable four-line poem plans from full Tet4 source material."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = "/media/zafkiel/WORK_SPACE2/models/Qwen3-8B"
DEFAULT_INPUT = ROOT / "data" / "sft" / "tet4_source_material_corpus_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "sft" / "tet4_plan_pilot_v1.jsonl"


def render_prompt(tokenizer, source: dict) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Bạn là biên tập viên thơ Lục Bát tiếng Việt. Đọc bài thơ nguồn và chỉ xuất JSON hợp lệ, "
                "không dùng thẻ think, không giải thích. Không chép lại câu thơ nguồn."
            ),
        },
        {
            "role": "user",
            "content": "\n".join([
                "Mục tiêu: lập dàn ý mềm để sau đó sáng tác MỘT lời chúc Tết Lục Bát đúng 4 dòng.",
                "Hãy rút tinh thần và hình ảnh của bài nguồn, nhưng không mô phỏng tác giả hay sao chép câu chữ.",
                "Schema JSON bắt buộc:",
                '{"recipient":"...", "wish_intent":"...", "keywords":["..."], "imagery":["..."], "tone":"...", "line_plan":["dòng 1 ...", "dòng 2 ...", "dòng 3 ...", "dòng 4 ..."]}',
                "Mỗi line_plan là vai trò ngữ nghĩa, không phải câu thơ hoàn chỉnh. Dòng 4 phải có khả năng khép ý.",
                "Bài thơ nguồn:",
                source["text"],
            ]),
        },
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)


def parse_json(text: str):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    required = {"recipient", "wish_intent", "keywords", "imagery", "tone", "line_plan"}
    return value if required <= set(value) and isinstance(value.get("line_plan"), list) and len(value["line_plan"]) == 4 else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--min-lines", type=int, default=5)
    parser.add_argument("--max-new-tokens", type=int, default=220)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    records = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line]
    selected = [
        row for row in records
        if row["unit_type"] == "raw_labeled_full_poem" and len(row["text"].splitlines()) >= args.min_lines
    ][:args.limit]
    if not selected:
        raise ValueError("Không có full poem phù hợp cho plan pilot")
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map={"": 0}, trust_remote_code=True, torch_dtype=torch.bfloat16)
    model.eval()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    outputs = []
    for index, source in enumerate(selected, start=1):
        prompt = render_prompt(tokenizer, source)
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.no_grad():
            generated = model.generate(**inputs, do_sample=False, max_new_tokens=args.max_new_tokens, eos_token_id=tokenizer.eos_token_id, pad_token_id=tokenizer.eos_token_id)
        raw = tokenizer.decode(generated[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        plan = parse_json(raw)
        output = {
            "pilot_id": f"PLAN-{index:03d}",
            "source_material_id": source["material_id"],
            "source_url": source.get("url"),
            "source_category": source.get("category"),
            "source_label": source.get("source_label"),
            "source_text": source["text"],
            "plan_raw": raw,
            "plan": plan,
            "plan_parse_ok": plan is not None,
            "review_decision": "",
            "review_notes": "",
            "usage": "plan_pilot_only_not_sft",
        }
        outputs.append(output)
        args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in outputs), encoding="utf-8")
        print(f"[{index}/{len(selected)}] {output['pilot_id']} parse_ok={output['plan_parse_ok']}", flush=True)
    audit_path = args.output.with_name(args.output.stem + "_audit.json")
    audit_path.write_text(json.dumps({"count": len(outputs), "parse_ok": sum(row["plan_parse_ok"] for row in outputs), "seed": args.seed, "model": args.model, "input": str(args.input), "selection": "raw_labeled_full_poem with min_lines", "not_sft": True}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
