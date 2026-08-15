import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from phonetics import is_valid_vietnamese_syllable


def filter_rhyme_dictionary(input_file: str, output_file: str, min_frequency: int = 2):
    """
    Lọc nhiễu từ điển vần:
    1. Giữ lại các cặp từ gieo vần có tần suất >= min_frequency.
    2. Loại bỏ cặp từ chứa token rác (không phải âm tiết tiếng Việt hợp lệ):
       - Từ có > 1 dấu thanh trong NFD (vd "đầụ", "gầntừng", "bề̀").
       - Từ chứa ký tự ngoài bảng chữ cái tiếng Việt (số, punctuation, ký tự lạ).
    3. Tái lập rhyme_groups chỉ từ các từ còn sống sót.
    """
    if not os.path.exists(input_file):
        print(f"❌ File không tồn tại: {input_file}")
        return

    print(f"🧹 Đang tiến hành lọc nhiễu từ điển: {input_file} (Ngưỡng tần suất >= {min_frequency})...")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_pairs = data.get("cooccurring_pairs", [])
    raw_groups = data.get("rhyme_groups", {})

    # Lọc cặp từ: (1) tần suất >= min_frequency, (2) cả 2 từ đều là âm tiết hợp lệ
    filtered_pairs = []
    removed_dirty = 0
    for p in raw_pairs:
        if p["frequency"] < min_frequency:
            continue
        if not is_valid_vietnamese_syllable(p["word1"]) or not is_valid_vietnamese_syllable(p["word2"]):
            removed_dirty += 1
            continue
        filtered_pairs.append(p)

    # Thu thập tập hợp các từ hợp lệ
    valid_words_set = set()
    for p in filtered_pairs:
        valid_words_set.add(p["word1"])
        valid_words_set.add(p["word2"])

    # Lọc lại rhyme_groups: chỉ giữ từ thuộc valid_words_set
    cleaned_groups = {}
    for group, words in raw_groups.items():
        valid_words_in_group = [w for w in words if w in valid_words_set]
        if valid_words_in_group:
            cleaned_groups[group] = sorted(valid_words_in_group)

    clean_data = {
        "total_couplets_analyzed": data.get("total_couplets_analyzed", 0),
        "min_frequency_threshold": min_frequency,
        "unique_rhyme_groups_count": len(cleaned_groups),
        "unique_rhyme_pairs_count": len(filtered_pairs),
        "total_valid_rhyme_words": len(valid_words_set),
        "rhyme_groups": cleaned_groups,
        "cooccurring_pairs": filtered_pairs,
    }

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2)

    print(f"\n================ BÁO CÁO LỌC NHIỄU ================")
    print(f"🔤 Cặp từ ban đầu: {len(raw_pairs):,} ➔ Sau lọc (>= {min_frequency}): {len(filtered_pairs):,} cặp từ ({len(filtered_pairs)/max(len(raw_pairs),1)*100:.1f}%)")
    print(f"🗑️  Cặp từ bị loại do token rác: {removed_dirty:,}")
    print(f"🎵 Số nhóm vần sạch: {len(cleaned_groups)}")
    print(f"📖 Số từ tiếng Việt chuẩn vần: {len(valid_words_set):,} từ")
    print(f"✓ Đã xuất từ điển sạch vào: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lọc nhiễu từ điển vần Lục Bát")
    parser.add_argument("--input", default="data/processed/master_rhyme_dictionary.json",
                        help="File từ điển vần gốc (master)")
    parser.add_argument("--output", default="data/processed/clean_rhyme_dictionary.json",
                        help="File từ điển sạch xuất ra")
    parser.add_argument("--min-frequency", type=int, default=2,
                        help="Ngưỡng tần suất tối thiểu (mặc định 2)")
    args = parser.parse_args()

    filter_rhyme_dictionary(args.input, args.output, min_frequency=args.min_frequency)
