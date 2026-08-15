import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from phonetics.tone_classifier import (
    get_tone,
    is_bang,
    is_trac,
    is_duong_binh,
    is_am_binh,
    ToneType
)

def test_tone_classification():
    # Thanh Ngang (Bằng - Dương bình)
    assert get_tone("trời") == ToneType.HUYEN
    assert get_tone("mây") == ToneType.NGANG
    assert get_tone("thu") == ToneType.NGANG
    assert get_tone("cao") == ToneType.NGANG

    # Thanh Huyền (Bằng - Âm bình)
    assert get_tone("người") == ToneType.HUYEN
    assert get_tone("về") == ToneType.HUYEN
    assert get_tone("thềm") == ToneType.HUYEN

    # Thanh Trắc
    assert get_tone("nắng") == ToneType.SAC
    assert get_tone("cả") == ToneType.HOI
    assert get_tone("bão") == ToneType.NGA
    assert get_tone("bạn") == ToneType.NANG

def test_is_bang_and_trac():
    bang_words = ["trời", "mây", "người", "về", "thu", "thềm", "phong", "trần"]
    trac_words = ["bắt", "phải", "mới", "được", "thân", "đã", "chối"]

    for w in bang_words:
        assert is_bang(w), f"Từ '{w}' phải thuộc thanh Bằng"
        assert not is_trac(w), f"Từ '{w}' không phải thanh Trắc"

    for w in ["bắt", "phải", "mới", "được", "đã"]:
        assert is_trac(w), f"Từ '{w}' phải thuộc thanh Trắc"
        assert not is_bang(w), f"Từ '{w}' không phải thanh Bằng"

def test_duong_binh_and_am_binh():
    # Dương bình (Ngang) vs Âm bình (Huyền)
    assert is_duong_binh("mây")
    assert not is_am_binh("mây")

    assert is_am_binh("người")
    assert not is_duong_binh("người")

if __name__ == "__main__":
    print("=== Đang chạy unit tests cho Tone Classifier ===")
    test_tone_classification()
    print("✓ test_tone_classification: PASSED")
    test_is_bang_and_trac()
    print("✓ test_is_bang_and_trac: PASSED")
    test_duong_binh_and_am_binh()
    print("✓ test_duong_binh_and_am_binh: PASSED")
    print("🎉 Tất cả test trong test_tone_classifier.py đều PASSED 100%!")
