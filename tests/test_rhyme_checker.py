import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from phonetics.rhyme_checker import (
    do_rhyme,
    extract_rhyme,
    rhyme_match_kind,
    rhymes_match_extracted,
)

def test_extract_rhyme():
    assert extract_rhyme("cành") == "anh"
    assert extract_rhyme("hành") == "anh"
    assert extract_rhyme("trời") == "ơi"
    assert extract_rhyme("người") == "ươi"
    assert extract_rhyme("thu") == "u"
    assert extract_rhyme("sương") == "ương"

def test_do_rhyme_exact():
    assert do_rhyme("cành", "hành")
    assert do_rhyme("thu", "ru")
    assert do_rhyme("sương", "thương")
    assert not do_rhyme("cành", "sương")

def test_do_rhyme_slant():
    # Vần thông / vần na ná
    assert do_rhyme("trời", "người")
    assert do_rhyme("thềm", "đêm")
    assert do_rhyme("mùa", "chùa")

def test_do_rhyme_strict():
    # strict=True: chỉ vần chính (khớp 100%)
    assert do_rhyme("cành", "hành", strict=True)
    assert not do_rhyme("trời", "người", strict=True)  # "ơi" vs "ươi" chỉ vần thông
    assert not do_rhyme("anh", "lang", strict=True)    # chỉ khớp qua SLANT_RHYME_MAP

def test_do_rhyme_slant_map_branch():
    # Nhánh SLANT_RHYME_MAP: "anh" -> "ang"
    assert do_rhyme("anh", "lang")
    assert do_rhyme("xanh", "bàng")  # "anh" vs "ang" qua map
    # Nhánh last-2-char fallback: "ơi" vs "ươi"
    assert do_rhyme("trời", "người")

def test_extract_rhyme_idempotent_battery():
    # extract_rhyme phải idempotent trên tập vần đã trích
    extracted = ["an", "ân", "ua", "uôn", "ơn", "iên", "oai", "ai", "ưa", "ang", "ương"]
    for r in extracted:
        assert extract_rhyme(extract_rhyme(r)) == extract_rhyme(r), f"non-idempotent: {r}"

def test_do_rhyme_same_as_pre_extracted():
    # do_rhyme(a, b) phải bằng rhymes_match_extracted(extract(a), extract(b))
    # regression: ngăn việc do_rhyme tái trích vần làm đổi kết quả.
    battery = [
        ("buồn", "luôn"),
        ("sương", "đường"),
        ("hoa", "loà"),
        ("tuấn", "xuân"),
        ("xoài", "toài"),
        ("mùa", "chùa"),
        ("uẩn", "xuẩn"),
        ("cành", "hành"),
        ("trời", "người"),
        ("thềm", "đêm"),
    ]
    for a, b in battery:
        assert do_rhyme(a, b) == rhymes_match_extracted(extract_rhyme(a), extract_rhyme(b)), f"mismatch: {a}, {b}"
        assert do_rhyme(a, b, strict=True) == rhymes_match_extracted(
            extract_rhyme(a), extract_rhyme(b), strict=True
        ), f"mismatch strict: {a}, {b}"

def test_rhymes_match_extracted_never_reextracts():
    # Vần đã trích phải so sánh trực tiếp, không đi qua extract_rhyme nữa.
    assert rhymes_match_extracted("uân", "ân")  # "uân" (extracted) vs "ân"
    # "au" -> "âu" qua SLANT_RHYME_MAP (vần thông â)
    assert rhymes_match_extracted("au", "âu")
    assert not rhymes_match_extracted("", "an")
    assert not rhymes_match_extracted("ua", "")

def test_do_rhyme_vantong_a():
    # Vần thông â (a ngắn/dài) — cực phổ biến trong Lục Bát, phải khớp.
    # Truyện Kiều: "khéo là ghét nhau" / "bể dâu" / "đau đớn"
    assert do_rhyme("nhau", "dâu")
    assert do_rhyme("dâu", "đau")
    assert do_rhyme("vàng", "tầng")
    assert do_rhyme("cam", "câm")
    assert do_rhyme("tan", "tần")
    # Vần thông e/ê, o/ô
    assert do_rhyme("hè", "bê")
    assert do_rhyme("no", "cô")


def test_rhyme_gold_classification_and_rejections():
    assert rhyme_match_kind("cành", "hành") == "exact"
    assert rhyme_match_kind("trời", "người") == "slant"
    assert rhyme_match_kind("vàng", "tầng") == "slant"
    assert rhyme_match_kind("sang", "rừng") is None
    assert rhyme_match_kind("tình", "xanh") is None
    assert not do_rhyme("sang", "rừng")
    assert not do_rhyme("tình", "xanh")


if __name__ == "__main__":
    print("=== Đang chạy unit tests cho Rhyme Checker ===")
    test_extract_rhyme()
    print("✓ test_extract_rhyme: PASSED")
    test_do_rhyme_exact()
    print("✓ test_do_rhyme_exact: PASSED")
    test_do_rhyme_slant()
    print("✓ test_do_rhyme_slant: PASSED")
    test_do_rhyme_strict()
    print("✓ test_do_rhyme_strict: PASSED")
    test_do_rhyme_slant_map_branch()
    print("✓ test_do_rhyme_slant_map_branch: PASSED")
    test_extract_rhyme_idempotent_battery()
    print("✓ test_extract_rhyme_idempotent_battery: PASSED")
    test_do_rhyme_same_as_pre_extracted()
    print("✓ test_do_rhyme_same_as_pre_extracted: PASSED")
    test_rhymes_match_extracted_never_reextracts()
    print("✓ test_rhymes_match_extracted_never_reextracts: PASSED")
    test_do_rhyme_vantong_a()
    print("✓ test_do_rhyme_vantong_a: PASSED")
    print("🎉 Tất cả test trong test_rhyme_checker.py đều PASSED 100%!")
