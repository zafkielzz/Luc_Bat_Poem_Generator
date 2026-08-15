#!/usr/bin/env python3
"""Build one provenance-preserving Tet4 source-material corpus without slicing poems.

The output is intentionally not an SFT dataset.  It stores full user-pasted
poems/source groups plus prior excerpts as material for later planning and
human-guided dataset construction.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "sft" / "tet4_source_material_corpus_v1.jsonl"
AUDIT = ROOT / "data" / "sft" / "tet4_source_material_corpus_v1_audit.json"
MANUAL_RAW = ROOT / "data" / "sft" / "tet4_manual_submission_TEMPLATE.md"
LABELED_RAW = ROOT / "data" / "sft" / "Nguồn https www dienmayxanh.txt"
LEGACY = (
    (ROOT / "data" / "sft" / "archive" / "tet4_legacy_staging_v1" / "tet4_combined_staging_v1.jsonl", "legacy_strict_excerpt"),
    (ROOT / "data" / "sft" / "archive" / "tet4_legacy_staging_v1" / "tet4_web_review_v1.jsonl", "legacy_web_review_excerpt"),
    (ROOT / "data" / "sft" / "archive" / "tet4_legacy_staging_v1" / "tet4_manual_review_v1.jsonl", "legacy_manual_review_excerpt"),
    (ROOT / "data" / "sft" / "archive" / "tet4_legacy_staging_v1" / "tet4_manual_short_v1.jsonl", "legacy_short_poem"),
)


def normalized_hash(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower().strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def add(candidates: list[dict], *, text: str, unit_type: str, source_id: str, url: str | None, author: str | None = None, **extra) -> None:
    text = unicodedata.normalize("NFC", text).strip()
    if not text:
        return
    candidates.append({
        "material_id": "tet4-material:" + normalized_hash(text)[:20],
        "source_id": source_id,
        "unit_type": unit_type,
        "url": url,
        "author": author,
        "text": text,
        "text_sha256": normalized_hash(text),
        "training_eligible": False,
        "usage": "source_material_only_not_direct_sft",
        **extra,
    })


def main() -> None:
    from scripts.import_tet4_manual_paste import chunks
    from scripts.import_tet4_labeled_source import parse

    candidates: list[dict] = []
    for index, (url, author, lines) in enumerate(chunks(MANUAL_RAW), start=1):
        add(candidates, text="\n".join(lines), unit_type="raw_manual_source_group", source_id="tet4_manual_paste_v1", url=url, author=author, source_group_index=index)
    for index, poem in enumerate(parse(LABELED_RAW), start=1):
        add(candidates, text="\n".join(poem["lines"]), unit_type="raw_labeled_full_poem", source_id="tet4_labeled_user_paste_v1", url=poem["url"], category=poem.get("category"), source_label=poem.get("label"), source_poem_index=index)
    for path, unit_type in LEGACY:
        if not path.exists():
            continue
        for record in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line):
            add(candidates, text=record["text"], unit_type=unit_type, source_id=record.get("source_id", "unknown"), url=record.get("url"), author=record.get("author"), source_work_id=record.get("source_work_id"), source_record_id=record.get("source_record_id"), metrics=record.get("metrics"), review_reason=record.get("review_reason"))

    merged: dict[str, dict] = {}
    for candidate in candidates:
        key = candidate["text_sha256"]
        if key not in merged:
            candidate["source_refs"] = [{"source_id": candidate["source_id"], "url": candidate["url"], "unit_type": candidate["unit_type"]}]
            merged[key] = candidate
        else:
            merged[key]["source_refs"].append({"source_id": candidate["source_id"], "url": candidate["url"], "unit_type": candidate["unit_type"]})
    records = sorted(merged.values(), key=lambda row: row["material_id"])
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records), encoding="utf-8")
    audit = {
        "version": "tet4-source-material-corpus-v1",
        "purpose": "full/raw material for later Qwen planning; not direct SFT",
        "candidate_records_before_exact_dedup": len(candidates),
        "unique_records": len(records),
        "exact_duplicates_merged": len(candidates) - len(records),
        "by_unit_type": dict(Counter(row["unit_type"] for row in records)),
        "output": str(OUT),
        "training_eligible": False,
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
