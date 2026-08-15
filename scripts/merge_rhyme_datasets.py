import json
import os
from collections import defaultdict

def merge_rhyme_files(file_paths, output_path):
    """
    Hợp nhất các bộ dữ liệu vần theo tần suất tự nhiên (tỷ lệ 1:1, không dùng trọng số).
    """
    merged_groups = defaultdict(set)
    merged_pairs = defaultdict(int)
    total_couplets = 0

    for path in file_paths:
        if not os.path.exists(path):
            continue
        print(f"Loading {path}...")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            total_couplets += data.get("total_couplets_analyzed", 0)

            # Merge rhyme groups
            for group, words in data.get("rhyme_groups", {}).items():
                merged_groups[group].update(words)

            # Merge cooccurring pairs
            for item in data.get("cooccurring_pairs", []):
                pair_key = tuple(sorted([item["word1"], item["word2"]]))
                merged_pairs[pair_key] += item.get("frequency", 1)

    # Format output
    sorted_groups = {g: sorted(list(words)) for g, words in merged_groups.items()}
    sorted_pairs = [
        {"word1": k[0], "word2": k[1], "frequency": v}
        for k, v in sorted(merged_pairs.items(), key=lambda x: x[1], reverse=True)
    ]

    master_data = {
        "total_couplets_analyzed": total_couplets,
        "unique_rhyme_groups_count": len(sorted_groups),
        "unique_rhyme_pairs_count": len(sorted_pairs),
        "rhyme_groups": sorted_groups,
        "cooccurring_pairs": sorted_pairs
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(master_data, f, ensure_ascii=False, indent=2)

    print(f"✓ Đã hợp nhất dữ liệu tần suất tự nhiên tại {output_path}")
    print(f"  - Tổng số cặp câu: {total_couplets:,}")
    print(f"  - Nhóm vần: {len(sorted_groups)}")
    print(f"  - Cặp từ gieo vần độc lập: {len(sorted_pairs):,}")

if __name__ == "__main__":
    files = [
        "data/processed/truyenkieu_rhymes.json",
        "data/processed/parquet_rhymes.json",
        "data/processed/csv_rhymes.json"
    ]
    merge_rhyme_files(files, "data/processed/master_rhyme_dictionary.json")
