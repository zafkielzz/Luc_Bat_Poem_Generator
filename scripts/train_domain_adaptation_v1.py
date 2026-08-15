#!/usr/bin/env python3
"""Train the broad Lục Bát domain adapter with QLoRA (text-only LM loss)."""
import unsloth  # Must precede TRL/Transformers imports for Unsloth patching.

import argparse
import json
from datetime import datetime
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import set_seed
from trl import SFTConfig, SFTTrainer
from unsloth import FastLanguageModel

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = "/media/zafkiel/WORK_SPACE2/models/Qwen3-8B"
DATA_DIR = ROOT / "data" / "sft" / "archive" / "domain_adaptation_fsoft_v1" / "domain_adaptation_fsoft_v1"
OUTPUT_DIR = ROOT / "outputs" / "domain_adaptation_fsoft_v1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--train", type=Path, default=DATA_DIR / "train.jsonl")
    parser.add_argument("--dev", type=Path, default=DATA_DIR / "dev.jsonl")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-seq-length", type=int, default=256)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--max-steps", type=int, default=-1)
    args = parser.parse_args()
    if not args.train.exists() or not args.dev.exists():
        raise FileNotFoundError("Run build_domain_adaptation_dataset.py first")

    set_seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset = load_dataset("json", data_files={"train": str(args.train), "dev": str(args.dev)})
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model, max_seq_length=args.max_seq_length, load_in_4bit=True
    )
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
    model.config.use_cache = False

    def add_eos(example):
        return {"text": example["text"] + tokenizer.eos_token}

    dataset = dataset.map(add_eos, remove_columns=dataset["train"].column_names)
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
        eval_strategy="no",
        save_strategy="epoch",
        save_total_limit=1,
        report_to="none",
        seed=args.seed,
        max_length=args.max_seq_length,
        packing=True,
        completion_only_loss=False,
        assistant_only_loss=False,
        eos_token=tokenizer.eos_token,
    )
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["dev"],
        args=config,
    )
    result = trainer.train()
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    run = {
        "version": "domain-adaptation-fsoft-v1",
        "date": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "train": str(args.train),
        "dev": str(args.dev),
        "seed": args.seed,
        "max_seq_length": args.max_seq_length,
        "epochs": args.epochs,
        "max_steps": args.max_steps,
        "learning_rate": args.learning_rate,
        "eos_token": tokenizer.eos_token,
        "lora": {"r": 16, "alpha": 16, "dropout": 0},
        "train_metrics": result.metrics,
    }
    (args.output_dir / "run_config.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(run, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
