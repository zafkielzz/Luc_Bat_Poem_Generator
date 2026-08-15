"""
Tiện ích kiểm tra tính hợp lệ của một ÂM TIẾT tiếng Việt.

Dùng để lọc token rác trong corpus:
- Token rác thường có > 1 dấu thanh (vd "đầụ" = dấu huyền + dấu nặng) hoặc
  là chuỗi nhiều âm tiết dính liền (vd "gầntừng" = 2 dấu huyền).
- "bề" HỢP LỆ dù có circumflex + grave — vì chỉ 1 dấu THANH (grave).
  Do đó điều kiện đúng là "số dấu thanh <= 1", không phải "số combining mark <= 1".
"""
import unicodedata
import re

# 5 dấu thanh tiếng Việt (dạng NFD) — dấu phụ nguyên âm (ă, â, ê, ô, ơ, ư) KHÔNG nằm trong đây.
TONE_MARKS = {'̀', '́', '̃', '̉', '̣'}

# Bảng chữ cái tiếng Việt viết thường (NFC) — mọi âm tiết hợp lệ chỉ gồm các ký tự này.
# KHÔNG gồm f/j/w/z: tiếng Việt không dùng các chữ này; nhận chúng khiến từ Anh
# 1-token như "just", "from", "wolf" lọt vào lexicon và sinh ra dòng thơ rác.
# Dải ASCII hợp lệ: a-d, e, g-i, k, l, m-n, o-q, r-s, t, u-v, x-y.
VIETNAMESE_ALPHABET_RE = re.compile(
    r'^[a-deg-iklmn-oqrstu-vx-yàáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩị'
    r'òóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]+$'
)

# Mặt chữ gốc của nguyên âm tiếng Việt trong NFD: ă, â → 'a'; ê → 'e'; ô, ơ → 'o'; ư → 'u'.
VIETNAMESE_VOWELS = set("aeiouy")

# Số chữ NGUYÊN ÂM GỐC (NFD) liên tiếp tối đa trong một âm tiết hợp lệ = 3.
# Thực tế tối đa: "ươi" (uo+i), "iêu" (ie+u), "uyê" (u+y+e), "oai", "hươu" (uo+u)...
# Mọi âm tiết có chuỗi >= 4 đều là rác: "thaoooooooo", "ơiiiii", "muười" (m+u+ươi dính),
# "rưượu" (u+ượu dính), "điiều" (đi+ều dính). "ượu" chỉ có 3 (uou) — là vần đúng của "rượu", giữ.
MAX_VOWEL_RUN = 3


def count_tone_marks(word: str) -> int:
    """Đếm số dấu thanh (0-2) trong một từ, dựa trên dạng NFD."""
    if not word:
        return 0
    nfd = unicodedata.normalize("NFD", word.lower())
    return sum(1 for ch in nfd if ch in TONE_MARKS)


def is_valid_vietnamese_syllable(word: str) -> bool:
    """
    Kiểm tra một chuỗi có phải âm tiết tiếng Việt hợp lệ hay không.
    - NFC-normalize, bỏ dấu câu 2 bên, lowercase.
    - Toàn ký tự thuộc bảng chữ cái tiếng Việt (không số, không punctuation).
    - Có đúng 0 hoặc 1 dấu thanh (loại "đầụ", "gầntừng", "bề̀").
    """
    if not word or not isinstance(word, str):
        return False
    cleaned = unicodedata.normalize("NFC", word.strip()).lower()
    if not cleaned:
        return False
    if not VIETNAMESE_ALPHABET_RE.match(cleaned):
        return False
    return count_tone_marks(cleaned) <= 1


def is_lexicon_syllable(word: str) -> bool:
    """
    Bộ lọc NGHIÊM cho âm tiết đưa vào từ điển sinh (syllables.json).

    Trên nền `is_valid_vietnamese_syllable`, loại tiếp 2 lớp rác làm vỡ chất
    lượng baseline (vowel-less fragments + chuỗi phụ âm của từ vay mượn/typo):
      1. Không có NGUYÊN ÂM nào — "b", "n", "h", "chk" (âm tiết tiếng Việt
         luôn có ít nhất 1 nguyên âm).
      2. Chuỗi phụ âm >= 3 — "angkor", "beings" (cấu trúc tiếng Việt: onset
         tối đa 2 phụ âm, ngoại lệ duy nhất "ngh"; coda tối đa 2).
      3. Chuỗi nguyên âm gốc (NFD) >= 4 — "thaoooooooo", "ơiiiii", "muười",
         "rưượu" (âm tiết tiếng Việt tối đa 3 nguyên âm gốc liên tiếp).
    """
    if not is_valid_vietnamese_syllable(word):
        return False
    nfd = unicodedata.normalize("NFD", word)
    base = "".join(c for c in nfd if not unicodedata.combining(c))
    # 1. Phải có nguyên âm.
    if not any(c in VIETNAMESE_VOWELS for c in base):
        return False
    # 2. Chuỗi phụ âm >= 3 chỉ hợp lệ nếu đúng onset "ngh" ở đầu âm tiết.
    run = 0
    for i, c in enumerate(base):
        if c in VIETNAMESE_VOWELS:
            run = 0
        else:
            run += 1
            if run >= 3 and base[:3] != "ngh":
                return False
    # 3. Chuỗi nguyên âm gốc liên tiếp >= 4 là rác (corpus lỗi/OCR/ghép chữ).
    vrun = 0
    for c in base:
        if c in VIETNAMESE_VOWELS:
            vrun += 1
            if vrun >= MAX_VOWEL_RUN + 1:
                return False
        else:
            vrun = 0
    return True
