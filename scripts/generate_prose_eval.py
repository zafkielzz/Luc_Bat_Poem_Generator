#!/usr/bin/env python3
"""Generate short Vietnamese prose for diagnostic evaluation without the poetry engine."""
import argparse
import csv
import json
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = "/media/zafkiel/WORK_SPACE2/models/Qwen3-8B"
DEFAULT_ADAPTER = ROOT / "outputs" / "sft_pilot_v1"
DEFAULT_RATINGS = ROOT / "data" / "evaluation" / "Bảng tính không có tiêu đề - paired_ratings_template.csv"
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "prose_sft_pilot_v1.csv"


def topic_from_poetry_prompt(prompt: str) -> str:
    text = prompt.strip()
    prefix = "viết bài thơ lục bát"
    if text.lower().startswith(prefix):
        text = text[len(prefix):].strip()
    import re
    text = re.sub(r"^\d+\s*(?:câu|dòng)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:về|tả|nhớ)\s+", "", text, flags=re.IGNORECASE)
    return text.rstrip(".")


def render_prompt(tokenizer, topic: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Bạn viết tiếng Việt tự nhiên, mạch lạc và giàu hình ảnh. "
                "Chỉ trả lời đúng yêu cầu, không dùng thẻ <think>, không giải thích cách làm."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Hãy viết một đoạn văn xuôi ngắn, khoảng 60–90 từ, về chủ đề: {topic}. "
                "Không làm thơ, không dùng gạch đầu dòng, không nhắc lại yêu cầu."
            ),
        },
    ]
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )


def load_records(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Không có prompt trong {path}")
    return [
        {
            "pair_id": row["pair_id"],
            "prompt_id": row["prompt_id"],
            "poetry_prompt": row["prompt"],
            "topic": topic_from_poetry_prompt(row["prompt"]),
        }
        for row in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh văn xuôi tiếng Việt để chẩn đoán model")
    parser.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--ratings", type=Path, default=DEFAULT_RATINGS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-new-tokens", type=int, default=150)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not (args.adapter / "adapter_config.json").is_file():
        raise FileNotFoundError(f"Không tìm thấy adapter: {args.adapter}")
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb,
        device_map={"": 0},
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model = PeftModel.from_pretrained(base_model, str(args.adapter))
    model.eval()

    rows = []
    for index, record in enumerate(load_records(args.ratings), 1):
        text = render_prompt(tokenizer, record["topic"])
        inputs = tokenizer(text, return_tensors="pt").to("cuda")
        with torch.no_grad():
            output = model.generate(
                **inputs,
                do_sample=True,
                temperature=args.temperature,
                top_p=args.top_p,
                repetition_penalty=1.05,
                max_new_tokens=args.max_new_tokens,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.eos_token_id,
            )
        answer = tokenizer.decode(
            output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
        ).strip()
        rows.append({**record, "response": answer, "rating": "", "notes": ""})
        print(f"[{index:02d}/{len(load_records(args.ratings)):02d}] {record['prompt_id']}: {answer[:90]}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["pair_id", "prompt_id", "poetry_prompt", "topic", "response", "rating", "notes"]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    metadata_path = args.output.with_suffix(".json")
    metadata_path.write_text(json.dumps({
        "version": "prose-diagnostic-v1",
        "adapter": str(args.adapter),
        "source_ratings": str(args.ratings),
        "seed": args.seed,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_new_tokens": args.max_new_tokens,
        "count": len(rows),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã lưu: {args.output}")


if __name__ == "__main__":
    main()
