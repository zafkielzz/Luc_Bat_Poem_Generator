import unicodedata
from enum import Enum
from typing import Optional

class ToneType(str, Enum):
    NGANG = "ngang"    # Không dấu (Bằng - Dương bình)
    HUYEN = "huyền"    # Dấu huyền (Bằng - Âm bình)
    SAC = "sắc"        # Dấu sắc (Trắc)
    HOI = "hỏi"        # Dấu hỏi (Trắc)
    NGA = "ngã"        # Dấu ngã (Trắc)
    NANG = "nặng"      # Dấu nặng (Trắc)
    UNKNOWN = "unknown"

# Mapping Unicode Combining Tone Marks (Decomposed Form NFD)
TONE_COMBINING_MAP = {
    '\u0300': ToneType.HUYEN, # Combining Grave Accent
    '\u0301': ToneType.SAC,   # Combining Acute Accent
    '\u0303': ToneType.NGA,   # Combining Tilde
    '\u0309': ToneType.HOI,   # Combining Hook Above
    '\u0323': ToneType.NANG,  # Combining Dot Below
}

def normalize_text(text: str) -> str:
    """Đưa chuỗi về chuẩn Unicode NFC và viết thường."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", text.strip().lower())

def get_tone(syllable: str) -> ToneType:
    """
    Xác định thanh điệu của một âm tiết tiếng Việt.
    Trả về thuộc tính ToneType (NGANG, HUYEN, SAC, HOI, NGA, NANG).
    """
    norm_syl = normalize_text(syllable)
    if not norm_syl:
        return ToneType.UNKNOWN

    # Tách chuỗi ra dạng NFD để tách riêng ký tự gốc và dấu thanh
    nfd_chars = unicodedata.normalize("NFD", norm_syl)
    for char in nfd_chars:
        if char in TONE_COMBINING_MAP:
            return TONE_COMBINING_MAP[char]

    # Nếu không tìm thấy dấu kết hợp (combining mark) -> Thanh Ngang (Không dấu)
    return ToneType.NGANG

def is_bang(syllable: str) -> bool:
    """Kiểm tra âm tiết có thuộc thanh BẰNG (Ngang hoặc Huyền) hay không."""
    tone = get_tone(syllable)
    return tone in (ToneType.NGANG, ToneType.HUYEN)

def is_trac(syllable: str) -> bool:
    """Kiểm tra âm tiết có thuộc thanh TRẮC (Sắc, Hỏi, Ngã, Nặng) hay không."""
    tone = get_tone(syllable)
    return tone in (ToneType.SAC, ToneType.HOI, ToneType.NGA, ToneType.NANG)

def is_duong_binh(syllable: str) -> bool:
    """Kiểm tra âm tiết có phải thanh NGANG (Dương bình) hay không."""
    return get_tone(syllable) == ToneType.NGANG

def is_am_binh(syllable: str) -> bool:
    """Kiểm tra âm tiết có phải thanh HUYỀN (Âm bình) hay không."""
    return get_tone(syllable) == ToneType.HUYEN
