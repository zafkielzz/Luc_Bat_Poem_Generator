#!/usr/bin/env python3
"""Stage 1.2: provenance-preserving Luc Bat staging, dedup and leakage-safe split."""
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "raw" / "fsoft_poem_generator_mit_v1" / "poems_dataset.csv"
DEFAULT_OUTPUT = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "staging_fsoft_v1.jsonl"
DEFAULT_STATS = ROOT / "data" / "sft" / "archive" / "wide_pilot_v1" / "staging_fsoft_v1_stats.json"
WS_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-zA-ZÀ-ỹĐđ]+")


def normalize_text(text):
    text = unicodedata.normalize("NFC", text or "").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(WS_RE.sub(" ", line).strip() for line in text.split("\n") if line.strip())


def normalize_genre(genre):
    return WS_RE.sub(" ", unicodedata.normalize("NFC", genre or "").strip().lower())


def simhash(text):
    weights = [0] * 64
    for token in set(TOKEN_RE.findall(text.lower())):
        value = int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")
        for bit in range(64):
            weights[bit] += 1 if value & (1 << bit) else -1
    return sum(1 << bit for bit, weight in enumerate(weights) if weight >= 0)


def hamming(left, right):
    return (left ^ right).bit_count()


class UnionFind:
    def __init__(self, ids):
        self.parent = {item: item for item in ids}

    def find(self, item):
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parent[max(left, right)] = min(left, right)


def load_luc_bat_rows(path, limit=None):
    rows, genres = [], Counter()
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            genre = normalize_genre(raw.get("genre", ""))
            genres[genre] += 1
            if genre != "luc bat":
                continue
            text = normalize_text(raw.get("content", ""))
            if not text:
                continue
            record_id = raw["id"].strip()
            rows.append({
                "source_id": "fsoft_poem_generator_mit_v1",
                "work_id": "fsoft:" + record_id,
                "source_record_id": record_id,
                "title": (raw.get("title") or "").strip(),
                "url": (raw.get("url") or "").strip(),
                "text": text,
            })
            if limit and len(rows) >= limit:
                break
    return rows, genres


def cluster_rows(rows, near_hamming=3, max_bucket_size=128):
    exact, exact_removed = {}, 0
    for row in rows:
        key = hashlib.sha256(row["text"].encode()).hexdigest()
        if key in exact:
            exact_removed += 1
        else:
            exact[key] = row
    unique = list(exact.values())
    ids = [row["work_id"] for row in unique]
    uf = UnionFind(ids)
    signatures = {row["work_id"]: simhash(row["text"]) for row in unique}
    buckets = defaultdict(list)
    for work_id, signature in signatures.items():
        for band in range(4):
            buckets[(band, (signature >> (band * 16)) & 0xFFFF)].append(work_id)

    links, skipped = 0, 0
    for members in buckets.values():
        if len(members) < 2:
            continue
        if len(members) > max_bucket_size:
            skipped += 1
            continue
        for index, left in enumerate(members):
            for right in members[index + 1:]:
                if hamming(signatures[left], signatures[right]) <= near_hamming:
                    if uf.find(left) != uf.find(right):
                        uf.union(left, right)
                        links += 1

    clusters = defaultdict(list)
    for row in unique:
        clusters[uf.find(row["work_id"])].append(row)
    for members in clusters.values():
        seed = min(item["work_id"] for item in members)
        cluster = "cluster-" + hashlib.sha256(seed.encode()).hexdigest()[:16]
        value = int(hashlib.sha256(cluster.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        split = "train" if value < 0.8 else "dev" if value < 0.9 else "test"
        for row in members:
            row["duplicate_cluster"], row["split"] = cluster, split
    return unique, {
        "input_rows": len(rows),
        "exact_duplicates_removed": exact_removed,
        "staging_rows": len(unique),
        "duplicate_clusters": len(clusters),
        "near_duplicate_links": links,
        "skipped_large_simhash_buckets": skipped,
        "split_counts": dict(Counter(row["split"] for row in unique)),
    }


def build(input_path, output_path, stats_path, limit=None):
    rows, genres = load_luc_bat_rows(input_path, limit)
    staged, stats = cluster_rows(rows)
    by_cluster = defaultdict(set)
    for row in staged:
        by_cluster[row["duplicate_cluster"]].add(row["split"])
    if any(len(splits) != 1 for splits in by_cluster.values()):
        raise RuntimeError("duplicate cluster leaked across split")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with Path(output_path).open("w", encoding="utf-8") as handle:
        for row in sorted(staged, key=lambda item: item["work_id"]):
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    stats.update({
        "version": "sft-staging-v1",
        "input": str(input_path),
        "input_sha256": hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
        "genre_counts": dict(genres),
        "selection_rule": "genre == luc bat",
        "split_rule": "sha256 duplicate cluster, 80/10/10",
        "near_duplicate_rule": "4 SimHash bands and Hamming distance <= 3",
    })
    Path(stats_path).write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output, args.stats, args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
