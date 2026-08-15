import unicodedata
from typing import Optional

from .tone_classifier import normalize_text


# Bảng gỡ dấu thanh, giữ nguyên dấu phụ nguyên âm (ă, â, ê, ô, ơ, ư, đ)
TONE_COMBINING_MARKS = {"\u0300", "\u0301", "\u0303", "\u0309", "\u0323"}

# Phụ âm đầu tiếng Việt phổ biến (xắp xếp theo độ dài giảm dần)
INITIAL_CONSONANTS = [
    "ngh", "tr", "th", "ch", "ph", "nh", "kh", "gh", "gi", "ng", "qu",
    "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "x",
]

# Ánh xạ chuẩn hóa vần thông về vần gốc. Chỉ những quan hệ liệt kê ở đây
# hoặc EXPLICIT_SLANT_PAIRS mới được chấp nhận; không suy diễn từ coda.
SLANT_RHYME_MAP = {
    # Vần i/y
    "y": "i", "ye": "ie", "ya": "ia",
    # Vần u/ư
    "uo": "ua", "uơ": "ưa",
    # Vần ê/e
    "e": "ê", "en": "ên", "et": "êt",
    # Vần ô/o
    "o": "ô", "on": "ôn", "ot": "ôt", "om": "ôm",
    # Vần thông â
    "au": "âu", "an": "ân", "am": "âm",
    # Vần nh/ng
    "anh": "ang", "ach": "ac", "inh": "ing", "ich": "ic",
}

# Quan hệ vần thông đối xứng không biểu diễn an toàn bằng canonical map một chiều.
# Mỗi pair được bảo vệ bằng gold test, tránh fallback trùng hai ký tự cuối.
EXPLICIT_SLANT_PAIRS = {
    frozenset(("ơi", "ươi")),  # trời / người
    frozenset(("ai", "oai")),  # ai / oai
    frozenset(("uân", "ân")),  # input đã trích vần, không re-extract
    frozenset(("ang", "âng")),  # vàng / tầng
}


def remove_tone_marks(text: str) -> str:
    """Loại dấu thanh, giữ dấu phụ của nguyên âm tiếng Việt."""
    norm_text = normalize_text(text)
    nfd_chars = unicodedata.normalize("NFD", norm_text)
    cleaned = "".join(c for c in nfd_chars if c not in TONE_COMBINING_MARKS)
    return unicodedata.normalize("NFC", cleaned)


def extract_rhyme(syllable: str) -> str:
    """Tách vần từ một âm tiết tiếng Việt."""
    cleaned = remove_tone_marks(syllable)
    if not cleaned:
        return ""

    lower_syl = cleaned.lower()
    for cons in INITIAL_CONSONANTS:
        if lower_syl.startswith(cons):
            cleaned = cleaned[len(cons):]
            break

    # Giữ phần vần chính cho các âm tiết có bán nguyên âm đầu.
    if (
        len(cleaned) > 2
        and cleaned[0] in ["u", "o"]
        and cleaned[1] in ["a", "e", "i", "o", "â", "ă"]
    ):
        cleaned = cleaned[1:]

    return cleaned


def rhyme_match_kind_extracted(
    r1: str, r2: str, strict: bool = False
) -> Optional[str]:
    """Phân loại hai vần đã trích thành exact, slant hoặc None."""
    if not r1 or not r2:
        return None

    if r1 == r2:
        return "exact"

    if strict:
        return None

    norm_r1 = SLANT_RHYME_MAP.get(r1, r1)
    norm_r2 = SLANT_RHYME_MAP.get(r2, r2)
    if norm_r1 == norm_r2:
        return "slant"

    if frozenset((r1, r2)) in EXPLICIT_SLANT_PAIRS:
        return "slant"

    return None


def rhyme_match_kind(syl1: str, syl2: str, strict: bool = False) -> Optional[str]:
    """Phân loại vần của hai âm tiết, không tái trích vần ở helper khác."""
    return rhyme_match_kind_extracted(
        extract_rhyme(syl1), extract_rhyme(syl2), strict=strict
    )


def rhymes_match_extracted(r1: str, r2: str, strict: bool = False) -> bool:
    """Kiểm tra hai vần đã trích có khớp chính hoặc vần thông đã chấp nhận."""
    return rhyme_match_kind_extracted(r1, r2, strict=strict) is not None


def do_rhyme(syl1: str, syl2: str, strict: bool = False) -> bool:
    """Kiểm tra hai âm tiết có gieo vần với nhau hay không."""
    return rhyme_match_kind(syl1, syl2, strict=strict) is not None
