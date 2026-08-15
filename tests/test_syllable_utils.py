"""Unit tests cho bộ lọc âm tiết (syllable_utils).

Trọng tâm: `is_lexicon_syllable` — bộ lọc NGHIÊM cho từ điển sinh, bảo đảm
baseline không tạo ra fragment ("n", "b", "ượu", "angkor").
"""
import pytest

from phonetics import is_lexicon_syllable, is_valid_vietnamese_syllable


# ---- is_valid_vietnamese_syllable (bộ lọc cơ bản, vẫn giữ) ----
class TestBaseValidator:
    @pytest.mark.parametrize("ok", [
        "bề",            # circumflex + grave nhưng chỉ 1 dấu THANH -> hợp lệ
        "trời", "hoa", "sáng", "thu", "xuân", "đường",
    ])
    def test_valid(self, ok):
        assert is_valid_vietnamese_syllable(ok)

    @pytest.mark.parametrize("bad", [
        "đầụ", "gầntừng", "bề̀",      # > 1 dấu thanh trong NFD
        "hoa.", "trời!", "123", "anh ơi",
    ])
    def test_invalid(self, bad):
        assert not is_valid_vietnamese_syllable(bad)


# ---- is_lexicon_syllable (bộ lọc nghiêm cho từ điển sinh) ----
class TestLexiconValidator:
    @pytest.mark.parametrize("ok", [
        # Các từ chức năng / âm tiết hợp lệ đủ mọi dạng cấu trúc
        "trời", "người", "thu", "sáng", "hoa", "xuân", "đường", "thương",
        "ướt", "uống", "yếu", "ước", "ương",       # zero-onset vowel-cluster HỢP LỆ
        "yêu", "iếc", "oài", "uất", "uyên", "ai", "ao", "âu", "ơi", "ôi", "ưa",
        "nghỉ", "nghề", "nghịch", "nghĩa",         # onset 3-phụ âm hợp lệ "ngh"
        "êm", "ẩm", "ếch", "anh", "oang", "tranh", "trường",
        # Chuỗi nguyên âm gốc (NFD) tối đa 3 — HỢP LỆ dù dài
        "ượu", "rượu", "hươu", "muốn", "khuya", "xoong", "uyến", "mười", "dưới",
        "ướt", "ương",
    ])
    def test_valid(self, ok):
        assert is_lexicon_syllable(ok)

    @pytest.mark.parametrize("bad", [
        # 1. Fragment không nguyên âm (vowel-less) — lỗi chính gây vỡ baseline
        "b", "n", "h", "chk", "xq", "tk",
        # 2. Chuỗi phụ âm >= 3 (từ vay mượn / typo) — không phải cấu trúc tiếng Việt
        "angkor", "beings", "bethlehem",
        # 3. Chữ ngoại lai f/j/w/z (tiếng Việt không dùng) — từ Anh lọt qua
        "just", "from", "eiffel", "wolf", "jazz", "weekend",
        # 4. Chuỗi NGUYÊN ÂM gốc (NFD) >= 4 — rác từ corpus lỗi/ghép chữ
        "thaoooooooo", "ơiiiii", "chiềuyêu", "yêuuu", "chaaaài", "thôiooi",
        "muười", "rưượu", "điiều", "ngươừi", "giưới", "tuổii", "haaaa", "giiữa",
        # 5. Rác cũ: > 1 dấu thanh
        "đầụ", "gầntừng", "bề̀",
    ])
    def test_invalid(self, bad):
        assert not is_lexicon_syllable(bad)

    def test_abbrev_foreign_handled_by_freq(self):
        # "cty" (c+ty, 'y' là nguyên âm): về cấu trúc vẫn "hợp lệ" -> KHÔNG phải
        # việc của bộ lọc cấu trúc, mà của tầng lọc tần suất/blocklist trong
        # build_syllable_vocab (FOREIGN_FUNCTION_WORDS).
        assert is_lexicon_syllable("cty")

    def test_valid_implied_by_base(self):
        # Mọi âm tiết hợp lệ theo is_lexicon_syllable cũng hợp lệ theo bộ lọc cơ bản.
        for w in ["trời", "ướt", "nghỉ", "uống"]:
            assert is_valid_vietnamese_syllable(w)
