import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from engine.lucbat_state import LucBatState, LineType

def test_lucbat_state_transitions():
    state = LucBatState()
    assert state.line_type == LineType.LUC
    assert state.word_pos == 1

    # Cặp 1 - Dòng Lục: "Ngẫm hay muôn sự tại trời" (6 chữ)
    luc1_words = ["Ngẫm", "hay", "muôn", "sự", "tại", "trời"]
    for w in luc1_words:
        state.step(w)

    assert state.rhyme_anchor_6 == "ơi"
    assert state.line_type == LineType.BAT

    # Cặp 1 - Dòng Bát: "Trời kia đã bắt làm người có thân" (8 chữ)
    bat1_words = ["Trời", "kia", "đã", "bắt", "làm", "người", "có", "thân"]
    bat1_constraints = []
    for w in bat1_words:
        bat1_constraints.append(state.get_constraint())
        state.step(w)

    # Kiểm tra ràng buộc câu Bát 1
    assert bat1_constraints[5].required_rhyme == "ơi"   # Tiếng 6 Bát vần với tiếng 6 Lục ("trời")
    assert bat1_constraints[7].required_tone == "NGANG" # Tiếng 6 Bát là Huyền ("người") -> Tiếng 8 Bát phải là Ngang ("thân")
    assert state.rhyme_anchor_8 == "ân"                 # Lưu vần tiếng 8 Bát ("thân" -> vần ân)

    # Chuyển sang Cặp 2 - Dòng Lục: "Bắt phong trần phải phong trần" (6 chữ)
    assert state.line_type == LineType.LUC
    luc2_words = ["Bắt", "phong", "trần", "phải", "phong", "trần"]
    luc2_constraints = []
    for w in luc2_words:
        luc2_constraints.append(state.get_constraint())
        state.step(w)

    # 🔥 KIỂM TRA ĐẶC BIỆT: Tiếng 6 của câu Lục tiếp theo phải gieo vần với tiếng 8 câu Bát trước!
    assert luc2_constraints[5].required_tone == "B"
    assert luc2_constraints[5].required_rhyme == "ân"  # Tiếng 6 Lục 2 ("trần") vần với tiếng 8 Bát 1 ("thân")!

if __name__ == "__main__":
    print("=== Đang chạy unit tests cho LucBat State Machine ===")
    test_lucbat_state_transitions()
    print("✓ test_lucbat_state_transitions: PASSED")
    print("🎉 Tất cả test trong test_lucbat_state.py đều PASSED 100%!")
