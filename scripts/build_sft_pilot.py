#!/usr/bin/env python3
"""Build a balanced, provenance-preserving no-CoT SFT pilot from quality data."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "quality_fsoft_v1.jsonl"
DEFAULT_TRAIN = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "pilot_train_v1.jsonl"
DEFAULT_DEV = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "pilot_dev_v1.jsonl"
DEFAULT_STATS = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "pilot_v1_stats.json"
STOP = {"bài", "thơ", "lục", "bát", "về", "và", "của", "cho", "một", "những", "trong", "người", "đời", "em", "anh", "tôi", "đã", "là", "có"}
WORD_RE = re.compile(r"[a-zA-ZÀ-ỹĐđ]+")


def rank(record):
    return hashlib.sha256(record["work_id"].encode()).hexdigest()


def title_topic(title):
    text = " ".join((title or "").split()).strip()
    if not text or text.lower() in {"null", "none", "bài thơ"}:
        return "thơ lục bát"
    return text[:160]


def keywords(text, limit=3):
    words = [word.lower() for word in WORD_RE.findall(text)]
    candidates = [word for word in words if len(word) >= 2 and word not in STOP]
    counts = Counter(candidates)
    return [word for word, _ in counts.most_common(limit)]


def messages_for(record):
    line_count = len(record["text"].splitlines())
    topic = title_topic(record["title"])
    meta = {
        "chủ đề": topic,
        "số câu": line_count,
        "từ khoá": keywords(record["text"]),
        "vần gợi ý": None,
    }
    user = "\n".join([
        "BÀI THƠ LỤC BÁT",
        "Chủ đề: " + meta["chủ đề"],
        "Số câu: " + str(meta["số câu"]) + " (mỗi câu Lục 6 âm tiết, Bát 8 âm tiết)",
        "Từ khoá: " + ", ".join(meta["từ khoá"]),
        "Sáng tác trực tiếp bài thơ, không giải thích, không suy luận.",
    ])
    system = "Bạn là một thi sĩ Việt Nam am hiểu thơ Lục Bát. Sáng tác trực tiếp bài thơ đúng luật, không dùng thẻ <think> và không giải thích."
    return meta, [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": record["text"]},
    ]


def select(records, split, target_size, lengths=(4, 6, 8)):
    quotas = {length: target_size // len(lengths) for length in lengths}
    for length in lengths[: target_size % len(lengths)]:
        quotas[length] += 1
    selected = []
    for length in lengths:
        pool = [row for row in records if row["split"] == split and len(row["text"].splitlines()) == length]
        chosen = sorted(pool, key=rank)[:quotas[length]]
        if len(chosen) != quotas[length]:
            raise ValueError(f"Insufficient {split} records with {length} lines")
        selected.extend(chosen)
    return sorted(selected, key=rank)


def write_records(records, path):
    with Path(path).open("w", encoding="utf-8") as target:
        for record in records:
            metadata, messages = messages_for(record)
            target.write(json.dumps({
                "messages": messages,
                "metadata": {
                    **metadata,
                    "source_id": record["source_id"],
                    "work_id": record["work_id"],
                    "duplicate_cluster": record["duplicate_cluster"],
                    "source_url": record["url"],
                    "quality_gate": record["quality_gate"],
                },
            }, ensure_ascii=False) + "\n")


def build(input_path, train_path, dev_path, stats_path, train_size=900, dev_size=180):
    records = [json.loads(line) for line in Path(input_path).open(encoding="utf-8")]
    train = select(records, "train", train_size)
    dev = select(records, "dev", dev_size)
    clusters = {record["duplicate_cluster"] for record in train}
    if clusters & {record["duplicate_cluster"] for record in dev}:
        raise RuntimeError("duplicate cluster leaked from train to dev")
    write_records(train, train_path)
    write_records(dev, dev_path)
    stats = {
        "version": "pilot-sft-v1",
        "source_quality_subset": str(input_path),
        "train_n": len(train),
        "dev_n": len(dev),
        "line_count_distribution": {
            "train": dict(Counter(len(row["text"].splitlines()) for row in train)),
            "dev": dict(Counter(len(row["text"].splitlines()) for row in dev)),
        },
        "selection": "deterministic SHA-256 work_id ranking, balanced 4/6/8 lines",
        "format": "chat messages; assistant output only contains poem; no chain of thought",
    }
    Path(stats_path).write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--dev", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--train-size", type=int, default=900)
    parser.add_argument("--dev-size", type=int, default=180)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.train, args.dev, args.stats, args.train_size, args.dev_size), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
