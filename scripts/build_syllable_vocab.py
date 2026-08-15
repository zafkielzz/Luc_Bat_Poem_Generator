"""
Xây danh sách âm tiết hợp lệ (syllables.json) cho precompute assets.

Nguồn gộp:
  1. Mọi từ trong `clean_rhyme_dictionary.json` (rhyme_groups).
  2. Mọi token tách theo whitespace từ toàn bộ corpus đã lọc thể loại
     Lục Bát (truyenkieu.txt + poem.csv + parquet) — để các vị trí "tự do"
     (1,3,5,7) có đủ từ chức năng/vốn từ không gieo vần.

Mỗi âm tiết được validate bằng `is_lexicon_syllable`:
  NFC, toàn ký tự tiếng Việt, <= 1 dấu thanh trong NFD (loại "đầụ", "gầntừng"),
  PHẢI có nguyên âm, chuỗi phụ âm <= 2 (loại "n", "angkor").

Ngoài ra, token từ corpus được lọc theo tần suất >= MIN_FREQ — loại các token
rác xuất hiện 1 lần từ dòng thơ hỏng/ghép chữ ("ượu", "ơiđã", "yêuthương")
mà vẫn lọt qua bộ lọc cấu trúc.
"""
import argparse
import json
import os
import string
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from phonetics import is_lexicon_syllable
from scripts.extract_rhymes_from_dataset import clean_poem_text, process_file_or_dataset

_PUNCT = string.punctuation + "“”‘’…–—"

# Nguồn corpus đã lọc genre (cùng logic với extract_rhymes_from_dataset.py)
DEFAULT_SOURCES = [
    "data/truyenkieu.txt",
    "data/poem.csv",
    "data/train-00000-of-00001.parquet",
]


def clean_token(word: str) -> str:
    return word.strip(_PUNCT).lower()


# Tần suất tối thiểu cho token lấy từ corpus — cùng tinh thần min_frequency của
# filter_noise.py: token xuất hiện 1 lần gần như chắc chắn là dòng thơ hỏng/ghép chữ.
MIN_FREQ = 2

# Từ tiếng Anh/từ ngoại lai 1-token vẫn lọt qua bộ lọc cấu trúc (đủ nguyên âm +
# chuỗi phụ âm ngắn) và xuất hiện ≥ 2 lần trong corpus nhạc/lyric hỗn hợp. Chặn thủ
# công để không sinh dòng thơ rác kiểu "ạt just a guy from the". (Chỉ từ chắc chắn
# KHÔNG phải âm tiết tiếng Việt — "in", "an", "so", "to", "no" là từ Việt thật, giữ.)
FOREIGN_FUNCTION_WORDS = {
    "the", "and", "guy", "led", "dien", "a", "i",
    "you", "your", "have", "has", "with", "this", "that",
    "they", "there", "not", "for", "are", "but", "his",
    "her", "she", "which", "will", "what", "who", "when",
}


def build_syllable_vocab(sources, dict_path: str, output_path: str, min_len: int = 1):
    start = time.time()

    # 1. Từ điển vần (đã qua filter_noise: tần suất >= 2, lọc >1 tone mark)
    with open(dict_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    words = set()
    for grp_words in data.get("rhyme_groups", {}).values():
        for w in grp_words:
            c = w.strip().lower()
            if c not in FOREIGN_FUNCTION_WORDS and is_lexicon_syllable(c):
                words.add(c)
    print(f"📖 Từ từ điển vần: {len(words):,}")

    # 2. Quét corpus — đếm tần suất token, validate sau bằng is_lexicon_syllable
    #    (nhanh hơn validate từng token trong vòng lặp ~26M lần).
    raw = Counter()
    for src in sources:
        if not os.path.exists(src):
            print(f"⚠️  Bỏ qua nguồn không tồn tại: {src}")
            continue
        blocks = process_file_or_dataset(src)
        n_blocks = len(blocks)
        for b in blocks:
            b = clean_poem_text(b)
            for tok in b.split():
                t = clean_token(tok)
                if len(t) >= min_len:
                    raw[t] += 1
        print(f"  ✓ {src}: {n_blocks:,} bài, {len(raw):,} token thô (lũy kế)")

    freq_ok = {w for w, c in raw.items() if c >= MIN_FREQ}
    valid = {w for w in freq_ok
             if w not in FOREIGN_FUNCTION_WORDS and is_lexicon_syllable(w)}
    words |= valid
    print(f"🔤 Token thô unique: {len(raw):,} -> tần suất ≥{MIN_FREQ}: "
          f"{len(freq_ok):,} -> hợp lệ: {len(valid):,}")

    result = sorted(words)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print(f"\n================ BÁO CÁO ÂM TIẾT ================")
    print(f"📦 Tổng âm tiết hợp lệ: {len(result):,}")
    print(f"✓ Đã lưu vào: {output_path}")
    print(f"⏱️  Thời gian: {time.time() - start:.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Xây danh sách âm tiết hợp lệ")
    ap.add_argument("--sources", nargs="*", default=DEFAULT_SOURCES,
                    help="Các file corpus (txt/csv/parquet)")
    ap.add_argument("--dict", default="data/processed/clean_rhyme_dictionary.json")
    ap.add_argument("--output", default="data/assets/syllables.json")
    ap.add_argument("--min-len", type=int, default=1)
    args = ap.parse_args()
    build_syllable_vocab(args.sources, args.dict, args.output, args.min_len)
