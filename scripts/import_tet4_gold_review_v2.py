#!/usr/bin/env python3
"""Promote reviewed Tet4 poems into a provenance-preserving Gold candidate set.

The raw review CSV is never changed except for human decisions.  This importer
creates a derived text for training: it removes decorative wrapper characters
while preserving the raw source text and all provenance.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.evaluator import LucBatEvaluator
from engine.lexical_guard import assess

DEFAULT_INPUT = ROOT / "data" / "evaluation" / "Review 168 bài để duyệt vào corpus - tet4_gold_review_v2.csv"
DEFAULT_OUTPUT = ROOT / "data" / "sft" / "tet4_gold_candidates_v1.jsonl"
DEFAULT_AUDIT = ROOT / "data" / "sft" / "tet4_gold_candidates_v1_audit.json"
DECISION_HEADERS = ("decision_accept_reject", "modecision_accept_reject")
ALLOWED_TONES = {"Chân thành", "Hài hước"}
RECIPIENT_ALIASES = {"chung chung": "mọi nhà"}
WRAPPER_RE = re.compile(r'[()"“”*]')
WS_RE = re.compile(r"[ \t]+")


def normalize_field(value: str | None) -> str:
    return WS_RE.sub(" ", unicodedata.normalize("NFC", value or "").strip())


def clean_poem_for_training(poem: str) -> str:
    """Remove decorative wrappers only; keep wording and normal punctuation."""
    lines = []
    for raw_line in unicodedata.normalize("NFC", poem or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = WS_RE.sub(" ", WRAPPER_RE.sub("", raw_line)).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def parse_keywords(raw: str | None) -> list[str]:
    keywords = [normalize_field(item) for item in (raw or "").split("|")]
    keywords = [item for item in keywords if item]
    folded = [item.casefold() for item in keywords]
    if len(keywords) not in (2, 3) or len(set(folded)) != len(folded):
        raise ValueError("keywords_pipe phải chứa 2 hoặc 3 keyword không trùng")
    return keywords


def decision_from(row: dict[str, str]) -> str:
    values = {normalize_field(row.get(header)).upper() for header in DECISION_HEADERS if row.get(header) is not None}
    values.discard("")
    if len(values) > 1:
        raise ValueError("hai cột quyết định mâu thuẫn")
    return values.pop() if values else ""


def canonical_recipient(recipient: str) -> str:
    return RECIPIENT_ALIASES.get(recipient.casefold(), recipient)


def recipient_scope(recipient: str) -> str:
    return "general" if recipient.casefold() in {"mọi nhà", "mọi người"} else "specific_or_group"


def build_prompt(recipient: str, keywords: list[str], tone: str) -> str:
    recipient = canonical_recipient(recipient)
    opening = (
        "Viết một bài thơ Lục Bát 4 dòng để chúc Tết cho mọi nhà."
        if recipient_scope(recipient) == "general"
        else f"Viết một bài thơ Lục Bát 4 dòng để chúc Tết cho {recipient}."
    )
    return f"{opening} Dùng tự nhiên các từ khóa: {', '.join(keywords)}. Giọng: {tone}."


def import_reviews(input_path: Path, output_path: Path, audit_path: Path) -> dict:
    evaluator = LucBatEvaluator()
    records: list[dict] = []
    rejected = Counter()
    seen_hashes: set[str] = set()

    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not any(header in reader.fieldnames for header in DECISION_HEADERS):
            raise ValueError("Không tìm thấy cột decision_accept_reject hoặc modecision_accept_reject")
        for row in reader:
            review_id = normalize_field(row.get("review_id"))
            if decision_from(row) != "ACCEPT":
                rejected["human_reject_or_unselected"] += 1
                continue
            try:
                recipient = normalize_field(row.get("recipient"))
                if not recipient:
                    raise ValueError("thiếu recipient")
                recipient = canonical_recipient(recipient)
                keywords = parse_keywords(row.get("keywords_pipe"))
                tone = normalize_field(row.get("tone"))
                if tone not in ALLOWED_TONES:
                    raise ValueError("tone phải là Chân thành hoặc Hài hước")
                raw_poem = unicodedata.normalize("NFC", row.get("poem") or "")
                poem = clean_poem_for_training(raw_poem)
                if not poem:
                    raise ValueError("thiếu poem")
            except ValueError as error:
                rejected[f"metadata:{error}"] += 1
                continue

            text_sha256 = hashlib.sha256(poem.encode("utf-8")).hexdigest()
            if text_sha256 in seen_hashes:
                rejected["exact_duplicate_after_cleaning"] += 1
                continue
            seen_hashes.add(text_sha256)
            metrics = evaluator.evaluate(poem, expected_num_lines=4)
            lexical = assess(poem, keywords)
            records.append({
                "review_id": review_id,
                "source_text": raw_poem,
                "text": poem,
                "prompt": build_prompt(recipient, keywords, tone),
                "recipient": recipient,
                "recipient_scope": recipient_scope(recipient),
                "wish_intent": normalize_field(row.get("wish_intent")),
                "keywords": keywords,
                "tone": tone,
                "source_id": normalize_field(row.get("source_id")),
                "author": normalize_field(row.get("author")) or None,
                "domain": normalize_field(row.get("domain")),
                "url": normalize_field(row.get("url")),
                "source_work_id": normalize_field(row.get("source_work_id")),
                "text_sha256": text_sha256,
                "metrics": metrics,
                "lexical_issues": lexical["issues"],
                "training_eligible": False,
                "promotion_status": "candidate_pending_content_and_dedup_audit",
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    audit = {
        "version": "tet4-gold-review-import-v1",
        "input": str(input_path),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "selection": "ACCEPT + recipient + 2-3 unique keywords + allowed tone; prompt is derived, never read from prompt_draft",
        "cleaning": "NFC, trim/collapse spaces, remove decorative parentheses, straight/curly quotes and asterisks; source_text remains untouched",
        "records_before_content_and_near_dedup_audit": len(records),
        "rejected_or_unselected": dict(sorted(rejected.items())),
        "structure_ok_after_cleaning": sum(record["metrics"]["structure_ok"] for record in records),
        "strict_valid_after_cleaning": sum(record["metrics"]["is_valid_lucbat"] for record in records),
        "lexical_pass_after_cleaning": sum(not record["lexical_issues"] for record in records),
        "recipient_scope_counts": dict(Counter(record["recipient_scope"] for record in records)),
        "note": "A candidate is not Gold/trainable until content-wish, near-dedup and source-work group-split audits complete.",
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    print(json.dumps(import_reviews(args.input, args.output, args.audit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
