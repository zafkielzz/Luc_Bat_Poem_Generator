import os
import json
import re
import string
from collections import defaultdict
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from phonetics import extract_rhyme, get_tone, is_bang

def clean_word(word: str) -> str:
    """Làm sạch từ, loại bỏ dấu câu."""
    return word.strip(string.punctuation + "“”‘’…–—").lower()

def clean_poem_text(text: str) -> str:
    """Loại bỏ tiền tố 'thơ lục bát:' ở đầu mỗi bài thơ."""
    if not text or not isinstance(text, str):
        return ""
    cleaned = re.sub(r'^(thơ\s+lục\s+bát\s*:?\s*)', '', text.strip(), flags=re.IGNORECASE)
    return cleaned.strip()

def parse_lucbat_couplets(text_content: str):
    """
    Tách nội dung thơ Lục Bát thành các cặp câu (Lục 6 chữ & Bát 8 chữ).
    """
    text_content = clean_poem_text(text_content)
    if not text_content:
        return []

    raw_lines = [line.strip() for line in text_content.split('\n') if line.strip()]
    lines = []

    for line in raw_lines:
        words = [clean_word(w) for w in line.split() if clean_word(w)]
        if len(words) in (6, 8):
            lines.append(words)

    couplets = []
    i = 0
    while i < len(lines) - 1:
        if len(lines[i]) == 6 and len(lines[i+1]) == 8:
            couplets.append((lines[i], lines[i+1]))
            i += 2
        else:
            i += 1

    return couplets

def process_file_or_dataset(file_path: str):
    """Đọc dữ liệu từ file .txt, .parquet hoặc .csv."""
    text_blocks = []

    if file_path.endswith(".parquet"):
        try:
            import pandas as pd
            print(f"📦 Đang nạp dataset Parquet: {file_path} ...")
            df = pd.read_parquet(file_path)

            # Lọc thể loại Lục Bát: parquet có cột the_loai với giá trị chuẩn "luc_bat".
            # KHÔNG lọc sẽ hút cả thơ 7 chữ / 8 chữ / 5 chữ vào corpus (bug cũ).
            genre_col = None
            for col in ["the_loai", "gender", "genre", "category"]:
                if col in df.columns:
                    genre_col = col
                    break

            if genre_col:
                before = len(df)
                df = df[df[genre_col].astype(str).str.strip().str.lower().eq("luc_bat")]
                print(f"  - Tổng số bài thơ trong Parquet: {before:,}")
                print(f"  - Số bài thơ Lục Bát (the_loai == 'luc_bat'): {len(df):,}")

            if "text" in df.columns:
                text_blocks = df["text"].dropna().tolist()
            else:
                text_blocks = df.iloc[:, 0].dropna().tolist()
            print(f"✓ Đã nạp thành công {len(text_blocks)} bài thơ Lục Bát từ Parquet!")
        except Exception as e:
            print(f"❌ Lỗi khi đọc file Parquet: {e}")
            return []

    elif file_path.endswith(".csv"):
        try:
            import pandas as pd
            print(f"📦 Đang nạp dataset CSV: {file_path} ...")
            df = pd.read_csv(file_path)

            # Lọc thể loại Lục Bát — EXACT MATCH "lục bát".
            # Không dùng contains() vì nó kéo cả "song thất lục bát" (thể khác) vào (bug cũ).
            genre_col = None
            for col in ["gender", "the_loai", "genre", "category"]:
                if col in df.columns:
                    genre_col = col
                    break

            if genre_col:
                print(f"🔍 Đang lọc riêng thể loại 'lục bát' từ cột '{genre_col}'...")
                df_filtered = df[df[genre_col].astype(str).str.strip().str.lower().eq("lục bát")]
                print(f"  - Tổng số bài thơ trong CSV: {len(df):,}")
                print(f"  - Số bài thơ LỤC BÁT chính thể (exact match): {len(df_filtered):,}")
                df = df_filtered

            content_col = "content" if "content" in df.columns else ("text" if "text" in df.columns else df.columns[0])
            text_blocks = df[content_col].dropna().tolist()
            print(f"✓ Đã sẵn sàng xử lý {len(text_blocks):,} bài thơ Lục Bát từ CSV!")

        except Exception as e:
            print(f"❌ Lỗi khi đọc file CSV: {e}")
            return []

    else:
        with open(file_path, "r", encoding="utf-8") as f:
            text_blocks = [f.read()]

    return text_blocks

def extract_rhymes_from_corpus(file_path: str, output_json_path: str):
    """
    Đọc dataset (.txt, .parquet hoặc .csv), lọc thể loại Lục Bát,
    trích xuất từ thứ 6 (Lục), thứ 6 (Bát), thứ 8 (Bát) và gộp vào danh sách vần.
    """
    if not os.path.exists(file_path):
        print(f"❌ File dataset không tồn tại: {file_path}")
        return

    text_blocks = process_file_or_dataset(file_path)
    if not text_blocks:
        print("❌ Không có dữ liệu để xử lý!")
        return

    rhyme_pairs = defaultdict(int)       # (word1, word2) -> count
    rhyme_group_words = defaultdict(set) # rhyme_pattern -> set of words
    total_couplets = 0

    print("⚡ Đang trích xuất vần và cặp từ Lục Bát...")
    for block in text_blocks:
        couplets = parse_lucbat_couplets(block)
        total_couplets += len(couplets)

        for idx, (luc, bat) in enumerate(couplets):
            w_l6 = luc[5]  # Tiếng thứ 6 câu Lục
            w_b6 = bat[5]  # Tiếng thứ 6 câu Bát
            w_b8 = bat[7]  # Tiếng thứ 8 câu Bát

            # Vần lưng 1: Tiếng 6 Lục & Tiếng 6 Bát
            if is_bang(w_l6) and is_bang(w_b6):
                pair_key = tuple(sorted([w_l6, w_b6]))
                rhyme_pairs[pair_key] += 1

                r_l6 = extract_rhyme(w_l6)
                r_b6 = extract_rhyme(w_b6)
                if r_l6: rhyme_group_words[r_l6].add(w_l6)
                if r_b6: rhyme_group_words[r_b6].add(w_b6)

            # Vần lưng 2: Tiếng 8 Bát cặp này & Tiếng 6 Lục cặp sau
            if idx < len(couplets) - 1:
                next_luc = couplets[idx+1][0]
                w_next_l6 = next_luc[5]
                if is_bang(w_b8) and is_bang(w_next_l6):
                    pair_key2 = tuple(sorted([w_b8, w_next_l6]))
                    rhyme_pairs[pair_key2] += 1

                    r_b8 = extract_rhyme(w_b8)
                    r_next = extract_rhyme(w_next_l6)
                    if r_b8: rhyme_group_words[r_b8].add(w_b8)
                    if r_next: rhyme_group_words[r_next].add(w_next_l6)

    # Chuyển đổi sang Dict lưu trữ
    processed_pairs = [
        {"word1": k[0], "word2": k[1], "frequency": v}
        for k, v in sorted(rhyme_pairs.items(), key=lambda x: x[1], reverse=False)
    ]

    grouped_dict = {
        pattern: sorted(list(words))
        for pattern, words in rhyme_group_words.items()
    }

    result = {
        "total_couplets_analyzed": total_couplets,
        "unique_rhyme_pairs_count": len(processed_pairs),
        "rhyme_groups_count": len(grouped_dict),
        "rhyme_groups": grouped_dict,
        "cooccurring_pairs": processed_pairs
    }

    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n================ BÁO CÁO TRÍCH XUẤT ================")
    print(f"📖 Tổng số cặp câu Lục - Bát đã phân tích: {total_couplets:,}")
    print(f"🎵 Số nhóm vần duy nhất: {len(grouped_dict)}")
    print(f"🔤 Số cặp từ gieo vần thực tế độc lập: {len(processed_pairs):,}")
    print(f"✓ Đã xuất dữ liệu làm sạch vào: {output_json_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "data/processed/combined_rhymes.json"
        extract_rhymes_from_corpus(input_file, output_file)
    else:
        print("Cú pháp: python scripts/extract_rhymes_from_dataset.py <file.parquet|file.csv|file.txt>")
