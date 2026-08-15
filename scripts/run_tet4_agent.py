#!/usr/bin/env python3
"""Chạy một lượt Tet4 agent: Qwen plan JSON -> logits-engine sinh/rerank thơ."""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.evaluator import LucBatEvaluator
from engine.lucbat_engine import LucBatLogitsProcessor
from engine.reranker import LucBatReranker
from engine.tet4_agent import Tet4Agent
from engine.tet4_coverage import coverage_instruction, evaluate_acceptance, retry_feedback
from engine.tet4_naturalness import build_critic_messages, parse_critic, repair_feedback
from engine.tet4_rhyme_scaffold import render_scaffold, resolve_scaffold
from engine.vocab_assets import LucBatVocabAssets
from scripts.generate_poem import build_prompt, generate_batch, load_cliches, render_chat_prompt

MODEL_PATH = "/media/zafkiel/WORK_SPACE2/models/Qwen3-8B"


def parse_plan(raw: str) -> dict[str, Any] | None:
    """Chỉ nhận JSON đủ schema; không âm thầm thay bằng template."""
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None
    try:
        plan = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    required = {"recipient", "wish_intent", "keywords", "imagery", "tone", "line_plan"}
    lines = plan.get("line_plan") if isinstance(plan, dict) else None
    if not isinstance(plan, dict) or not required <= plan.keys() or not isinstance(plan.get("imagery"), list) or not isinstance(lines, list) or len(lines) != 4:
        return None
    if not all(isinstance(line, dict) and {"line", "role", "idea", "image"} <= line.keys() for line in lines):
        return None
    return plan


def render_poetry_prompt(metadata: dict[str, Any], plan: dict[str, Any],
                         feedback: str | None = None) -> str:
    outline = [f"Dòng {item['line']}: {item['role']} — {item['idea']} (hình ảnh: {item['image']})"
               for item in plan["line_plan"]]
    parts = [build_prompt(metadata), coverage_instruction(metadata),
             "Dàn ý Qwen (chỉ định hướng, không chép nguyên câu):", *outline,
             render_scaffold(plan["rhyme_scaffold"])]
    if feedback:
        parts.append(feedback)
    parts.append("Viết trực tiếp đúng một bài thơ bốn dòng, không JSON, không giải thích, không <think>.")
    return "\n".join(parts)


def run_naturalness_critic(model, tokenizer, poem: str, metadata: dict[str, Any]) -> dict[str, Any]:
    messages = build_critic_messages(poem, metadata)
    prompt = render_chat_prompt(tokenizer, messages, enable_thinking=False)
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    with torch.no_grad():
        output = model.generate(**inputs, do_sample=False, max_new_tokens=160,
                                eos_token_id=tokenizer.eos_token_id,
                                pad_token_id=tokenizer.eos_token_id)
    raw = tokenizer.decode(output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
    return {"raw": raw, "result": parse_critic(raw)}


def strict_repair_feedback(item: dict[str, Any], metadata: dict[str, Any]) -> str:
    """Feedback repair ưu tiên evidence tất định; critic chỉ bổ sung nếu nó reject."""
    base = retry_feedback([item["acceptance"]], metadata)
    lexical_issues = item.get("lexical", {}).get("issues", [])
    deterministic = []
    for issue in lexical_issues:
        if issue.get("type") == "orphan_vowel":
            deterministic.append(f"không dùng âm tiết đứng riêng: {issue.get('token')}")
        elif issue.get("type") == "truncated_keyword":
            deterministic.append(f"không cắt keyword: {issue.get('keyword')}")
    critic = item.get("naturalness_critic", {}).get("result")
    critic_hint = repair_feedback(item["poem"], critic)
    parts = [base]
    if deterministic:
        parts.append("Lỗi tất định phải sửa: " + "; ".join(deterministic) + ".")
    if critic_hint:
        parts.append(critic_hint)
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tet4: Qwen plan JSON rồi logits-engine sinh thơ")
    parser.add_argument("wish_intent")
    parser.add_argument("--keywords", nargs="+", required=True)
    parser.add_argument("--model", default=MODEL_PATH)
    parser.add_argument("--num-samples", type=int, default=8)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--tone-penalty", type=float, default=1.5)
    parser.add_argument("--rhyme-penalty", type=float, default=3.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--plan-max-new-tokens", type=int, default=512)
    parser.add_argument("--max-plan-attempts", type=int, default=2)
    parser.add_argument("--plan-only", action="store_true",
                        help="Chỉ kiểm Qwen plan + rhyme scaffold, không sinh thơ.")
    parser.add_argument("--max-attempts", type=int, default=3,
                        help="soft, strict, rồi strict repair (mặc định).")
    parser.add_argument("--strict-form-retry", action="store_true", default=True,
                        help="Attempt cuối sau soft fail: hard-mask tone/rhyme bắt buộc.")
    parser.add_argument("--no-strict-form-retry", action="store_false", dest="strict_form_retry",
                        help="Tắt strict retry để chạy ablation soft-only.")
    parser.add_argument("--naturalness-critic", action="store_true", default=True,
                        help="Chấm strict candidate bằng Qwen trước repair.")
    parser.add_argument("--no-naturalness-critic", action="store_false", dest="naturalness_critic")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "agent_runs" / "latest.json")
    args = parser.parse_args()
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed); torch.cuda.manual_seed_all(args.seed)
    agent = Tet4Agent(); brief = agent.brainstorm(args.wish_intent)
    metadata = agent.select_keywords(args.wish_intent, args.keywords)

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map={"": 0}, trust_remote_code=True, torch_dtype=torch.bfloat16)
    model.eval()
    plan_raw = ""
    plan = None
    plan_attempts = []
    plan_feedback = None
    for plan_index in range(1, args.max_plan_attempts + 1):
        plan_messages = agent.build_plan_messages(brief, metadata)
        if plan_feedback:
            plan_messages[-1]["content"] += "\n" + plan_feedback
        plan_chat = render_chat_prompt(tokenizer, plan_messages, enable_thinking=False)
        plan_inputs = tokenizer(plan_chat, return_tensors="pt").to("cuda")
        with torch.no_grad():
            plan_ids = model.generate(**plan_inputs, do_sample=False, max_new_tokens=args.plan_max_new_tokens, eos_token_id=tokenizer.eos_token_id, pad_token_id=tokenizer.eos_token_id)
        plan_raw = tokenizer.decode(plan_ids[0][plan_inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        plan = parse_plan(plan_raw)
        plan_attempts.append({"attempt": plan_index, "feedback": plan_feedback,
                              "raw": plan_raw, "parse_ok": plan is not None})
        if plan is not None:
            break
        plan_feedback = (
            "Scaffold trước không hợp lệ. Hãy trả lại toàn bộ JSON, dùng đúng scaffold ví dụ "
            "xuân/xuân/nhà/qua/ca nếu không tự kiểm được ba quan hệ vần."
        )
    if plan is None:
        failure = {"seed": args.seed, "metadata": metadata, "creative_brief": brief.to_dict(), "plan_raw": plan_raw,
                   "plan_attempts": plan_attempts, "plan": None, "failure": "invalid_plan_or_rhyme_scaffold"}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise RuntimeError(f"Qwen không trả plan JSON hợp lệ; raw plan đã lưu tại {args.output}.")

    scaffold_resolution = resolve_scaffold(plan.get("rhyme_scaffold"))
    plan["rhyme_scaffold_proposed"] = plan.get("rhyme_scaffold")
    plan["rhyme_scaffold"] = scaffold_resolution["scaffold"]
    plan["rhyme_scaffold_source"] = scaffold_resolution["source"]

    if args.plan_only:
        result = {"seed": args.seed, "metadata": metadata, "creative_brief": brief.to_dict(),
                  "status": "plan_ready", "plan_raw": plan_raw, "plan_attempts": plan_attempts,
                  "plan": plan, "rhyme_scaffold_resolution": scaffold_resolution}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "plan": plan}, ensure_ascii=False, indent=2))
        print(f"Saved trace: {args.output}")
        return

    assets = LucBatVocabAssets.load(str(ROOT / "data" / "assets"))
    processor = LucBatLogitsProcessor(assets, tone_penalty=args.tone_penalty, rhyme_penalty=args.rhyme_penalty, stop_after_couplets=2, device="cuda")
    reranker = LucBatReranker(LucBatEvaluator(), load_cliches(), lexical_guard=True)
    feedback = None
    attempts = []
    accepted = []
    ranked = []
    for attempt_index in range(1, args.max_attempts + 1):
        strict_form = args.strict_form_retry and attempt_index >= 2
        active_rhyme_penalty = args.rhyme_penalty * (1.0 + 0.5 * (attempt_index - 1))
        processor.rhyme_penalty = active_rhyme_penalty
        processor.strict_tone = strict_form
        processor.strict_rhyme = strict_form
        poetry_prompt = render_poetry_prompt(metadata, plan, feedback)
        poems = generate_batch(model, tokenizer, processor, poetry_prompt, args.num_samples,
                               args.temperature, args.top_p, enable_thinking=False)
        ranked = reranker.rerank(poems, metadata)
        for item in ranked:
            item["acceptance"] = evaluate_acceptance(item, metadata)
        if strict_form and args.naturalness_critic:
            for item in ranked:
                item["naturalness_critic"] = run_naturalness_critic(model, tokenizer, item["poem"], metadata)
                critic = item["naturalness_critic"]["result"]
                if critic and critic["decision"] == "reject":
                    # Reject là veto một chiều: critic không bao giờ làm một
                    # bài pass, nhưng một lỗi tự nhiên rõ ràng phải bị chặn để
                    # đi sang repair. Accept không đủ tin cậy làm hard gate.
                    item["naturalness_critic"]["veto_reject"] = True
                    item["acceptance"]["pass"] = False
                    item["acceptance"]["reasons"].append("naturalness_critic_reject")
        accepted = [item for item in ranked if item["acceptance"]["pass"]]
        attempts.append({"attempt": attempt_index, "feedback": feedback,
                         "rhyme_penalty": active_rhyme_penalty,
                         "strict_tone": processor.strict_tone, "strict_rhyme": processor.strict_rhyme,
                         "strict_relaxations": processor.strict_relaxations,
                         "prompt": poetry_prompt, "ranked": ranked})
        if accepted:
            break
        feedback = (strict_repair_feedback(ranked[0], metadata)
                    if strict_form and ranked else
                    retry_feedback([item["acceptance"] for item in ranked], metadata))

    best = accepted[0] if accepted else None
    result = {"seed": args.seed, "metadata": metadata, "creative_brief": brief.to_dict(), "plan_raw": plan_raw,
              "plan_attempts": plan_attempts, "plan": plan,
              "rhyme_scaffold_resolution": scaffold_resolution,
              "status": "accepted" if best else "failed_acceptance_gate",
              "generation": {"logits_processor": {"hard": ["6-8 syllables", "newline", "syllable_trie"], "soft": ["tone", "rhyme"]},
                             "strict_form_retry": args.strict_form_retry,
                             "naturalness_critic": args.naturalness_critic,
                             "num_samples_per_attempt": args.num_samples, "max_attempts": args.max_attempts},
              "best": best, "diagnostic_best": ranked[0] if ranked else None, "attempts": attempts}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "plan": plan, "best": best,
                      "diagnostic_best": None if best else result["diagnostic_best"]}, ensure_ascii=False, indent=2))
    print(f"Saved trace: {args.output}")


if __name__ == "__main__":
    main()
