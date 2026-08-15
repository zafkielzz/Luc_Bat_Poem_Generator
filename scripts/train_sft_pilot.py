#!/usr/bin/env python3
"""Train the reproducible Stage 2 QLoRA pilot on no-CoT Luc Bat chat data."""
import argparse
import json
from datetime import datetime
from pathlib import Path

import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from transformers import set_seed
from trl import SFTConfig, SFTTrainer

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = "/media/zafkiel/WORK_SPACE2/models/Qwen3-8B"
TRAIN_PATH = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "pilot_train_v1.jsonl"
DEV_PATH = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "pilot_dev_v1.jsonl"
OUTPUT_DIR = ROOT / "outputs" / "sft_pilot_v1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--train", type=Path, default=TRAIN_PATH)
    parser.add_argument("--dev", type=Path, default=DEV_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-seq-length", type=int, default=256)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--eval-strategy", choices=["no", "steps"], default="no")
    args = parser.parse_args()

    set_seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset = load_dataset("json", data_files={"train": str(args.train), "dev": str(args.dev)})
    print("[pilot] Dataset loaded.", flush=True)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
    )
    print("[pilot] Base model loaded.", flush=True)
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
    )
    print("[pilot] LoRA adapters attached.", flush=True)
    model.config.use_cache = False

    def as_prompt_completion(example):
        messages = example["messages"]
        prompt = tokenizer.apply_chat_template(
            messages[:-1], tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        return {"prompt": prompt, "completion": messages[-1]["content"] + tokenizer.eos_token}

    columns = dataset["train"].column_names
    dataset = dataset.map(as_prompt_completion, remove_columns=columns)
    print("[pilot] Prompt/completion dataset prepared.", flush=True)
    config = SFTConfig(
        output_dir=str(args.output_dir),
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        warmup_ratio=0.05,
        lr_scheduler_type="cosine",
        optim="adamw_8bit",
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        logging_steps=5,
        eval_strategy=args.eval_strategy,
        eval_steps=20,
        save_strategy="epoch",
        save_total_limit=1,
        report_to="none",
        seed=args.seed,
        max_length=args.max_seq_length,
        packing=False,
        completion_only_loss=True,
        assistant_only_loss=False,
    )
    print("[pilot] Trainer configuration prepared.", flush=True)
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["dev"],
        args=config,
    )
    print("[pilot] Trainer initialized; starting training.", flush=True)
    result = trainer.train()
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    run = {
        "version": "pilot-qlora-v1",
        "date": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "train": str(args.train),
        "dev": str(args.dev),
        "seed": args.seed,
        "max_seq_length": args.max_seq_length,
        "epochs": args.epochs,
        "max_steps": args.max_steps,
        "learning_rate": args.learning_rate,
        "eval_strategy": args.eval_strategy,
        "lora": {"r": 16, "alpha": 16, "dropout": 0},
        "train_metrics": result.metrics,
    }
    (args.output_dir / "run_config.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(run, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
