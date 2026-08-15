import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.evaluator import LucBatEvaluator, _line_syllables

# 4 câu mở đầu Truyện Kiều — Lục Bát chuẩn 100%.
KIEU_GOOD = """Trăm năm trong cõi người ta
Chữ tài chữ mệnh khéo là ghét nhau
Trải qua một cuộc bể dâu
Những điều trông thấy mà đau đớn lòng"""

# Cùng bài nhưng làm hỏng cả 3 trục:
#  - dòng 2 thừa 1 chữ ("xa") -> SCR mất
#  - dòng 4 lệch thanh vị trí 4 ("thấy"->"trông") -> TCR mất
#  - dòng 3 đứt vần ("dâu"->"vần") -> RMA mất
KIEU_BROKEN = """Trăm năm trong cõi người ta
Chữ tài chữ mệnh khéo là ghét nhau xa
Trải qua một cuộc bể vần
Những điều trông trông mà đau đớn lòng"""


def test_kieu_good_scores_100():
    ev = LucBatEvaluator()
    res = ev.evaluate(KIEU_GOOD)
    assert res["scr"] == 100.0
    assert res["tcr"] == 100.0
    assert res["rma"] == 100.0
    assert res["overall"] == 100.0
    assert res["is_valid_lucbat"] is True
    assert res["num_lines"] == 4


def test_kieu_broken_lower_than_good():
    ev = LucBatEvaluator()
    good = ev.evaluate(KIEU_GOOD)
    bad = ev.evaluate(KIEU_BROKEN)

    assert bad["scr"] < good["scr"]
    assert bad["tcr"] < good["tcr"]
    assert bad["rma"] < good["rma"]
    assert bad["overall"] < good["overall"]
    assert bad["is_valid_lucbat"] is False

    # Kiểm tra số cụ thể để chặn hồi quy:
    # SCR = 3/4 dòng đúng 6/8 = 75; TCR = 9/10 = 90; RMA = 0 (vần duy nhất đứt)
    assert bad["scr"] == 75.0
    assert bad["tcr"] == 90.0
    assert bad["rma"] == 0.0
    assert bad["overall"] == 0.4 * 75 + 0.3 * 90  # = 57.0


def test_single_couplet():
    ev = LucBatEvaluator()
    res = ev.evaluate("Trăm năm trong cõi người ta\nChữ tài chữ mệnh khéo là ghét nhau")
    assert res["scr"] == 100.0
    assert res["tcr"] == 100.0
    assert res["rma"] == 100.0
    assert res["num_lines"] == 2


def test_prose_scores_zero_scr():
    # Văn xuôi / số chữ sai -> SCR thấp, không hợp lệ
    ev = LucBatEvaluator()
    res = ev.evaluate("Hôm nay trời đẹp và tôi đi dạo quanh hồ rất vui")
    assert res["scr"] == 0.0
    assert res["is_valid_lucbat"] is False


def test_line_detail_structure():
    ev = LucBatEvaluator()
    res = ev.evaluate("Trăm năm trong cõi người ta\nChữ tài chữ mệnh khéo là ghét nhau")
    line = res["lines"][0]
    assert line["count"] == 6
    assert line["is_correct_length"] is True
    assert line["correct_positions"] == 3      # B-T-B ở vị trí 2-4-6
    assert line["mandatory_positions"] == 3
    assert line["syllables"] == ["trăm", "năm", "trong", "cõi", "người", "ta"]

    line2 = res["lines"][1]
    assert line2["count"] == 8
    assert line2["correct_positions"] == 4     # B-T-B-(ngang vs huyền)
    assert line2["mandatory_positions"] == 4


def test_line_syllables_clean():
    # Dấu câu 2 bên bị bỏ, lowercase, NFC
    assert _line_syllables("Trời — xanh!") == ["trời", "xanh"]



def test_structure_rejects_all_luc_lines():
    ev = LucBatEvaluator()
    poem = "\n".join([KIEU_GOOD.split("\n")[0]] * 4)
    res = ev.evaluate(poem)
    assert res["scr"] == 50.0
    assert res["structure_ok"] is False
    assert res["rma"] == 0.0


def test_structure_rejects_bat_first_and_incomplete_couplet():
    ev = LucBatEvaluator()
    lines = KIEU_GOOD.split("\n")
    bat_first = ev.evaluate("\n".join(lines[:2][::-1]))
    incomplete = ev.evaluate("\n".join(lines[:3]))
    assert bat_first["scr"] == 0.0
    assert bat_first["structure_ok"] is False
    assert incomplete["scr"] == round(100 * 2 / 3, 2)
    assert incomplete["structure_ok"] is False
    assert incomplete["rma"] == 0.0


def test_expected_num_lines_is_part_of_structural_score():
    ev = LucBatEvaluator()
    res = ev.evaluate(KIEU_GOOD, expected_num_lines=6)
    assert res["scr"] == round(100 * 4 / 6, 2)
    assert res["structure_ok"] is False
    assert "line_count_mismatch" in res["structure_errors"]


def test_rhyme_breakdown_reports_exact_and_accepted_slant():
    ev = LucBatEvaluator()
    exact = ev.evaluate(KIEU_GOOD)
    slant = ev.evaluate(
        "Chiều về lặng ngắm mây trời\n"
        "Gió đưa câu hát cho người qua sông"
    )
    assert exact["exact_rma"] == round(100 / 3, 2)
    assert exact["slant_rma"] == round(200 / 3, 2)
    assert exact["combined_rma"] == 100.0
    assert slant["exact_rma"] == 0.0
    assert slant["slant_rma"] == 100.0
    assert slant["combined_rma"] == 100.0
    assert slant["rhyme_pairs"][0]["kind"] == "slant"


if __name__ == "__main__":
    print("=== Đang chạy unit tests cho Evaluator ===")
    test_kieu_good_scores_100()
    print("✓ test_kieu_good_scores_100: PASSED")
    test_kieu_broken_lower_than_good()
    print("✓ test_kieu_broken_lower_than_good: PASSED")
    test_single_couplet()
    print("✓ test_single_couplet: PASSED")
    test_prose_scores_zero_scr()
    print("✓ test_prose_scores_zero_scr: PASSED")
    test_line_detail_structure()
    print("✓ test_line_detail_structure: PASSED")
    test_line_syllables_clean()
    print("✓ test_line_syllables_clean: PASSED")
    print("🎉 Tất cả test trong test_evaluator.py đều PASSED 100%!")
