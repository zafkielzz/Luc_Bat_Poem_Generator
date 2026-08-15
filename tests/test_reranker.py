import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.evaluator import LucBatEvaluator
from engine.reranker import LucBatReranker, DEFAULT_WEIGHTS

KIEU_GOOD = """Trăm năm trong cõi người ta
Chữ tài chữ mệnh khéo là ghét nhau
Trải qua một cuộc bể dâu
Những điều trông thấy mà đau đớn lòng"""

KIEU_BROKEN = """Trăm năm trong cõi người ta
Chữ tài chữ mệnh khéo là ghét nhau xa
Trải qua một cuộc bể vần
Những điều trông trông mà đau đớn lòng"""

CLICHES = ["long lanh", "đong đầy", "bên thềm", "nắng vàng", "mênh mông", "ngọt ngào"]


class StubEvaluator:
    """Giả lập evaluator trả điểm cố định để cô lập các thành phần khác của reranker."""

    def __init__(self, overall: float = 100.0):
        self._overall = overall

    def evaluate(self, poem: str) -> dict:
        return {"overall": self._overall, "scr": self._overall, "tcr": self._overall,
                "rma": self._overall, "is_valid_lucbat": self._overall >= 100,
                "num_lines": len([l for l in poem.split("\n") if l.strip()]), "lines": []}


def _make(overall=100.0):
    return LucBatReranker(evaluator=StubEvaluator(overall), cliches=CLICHES)


def test_cliche_component_penalizes():
    rk = _make()
    clean = "Trời thu gió mát trăng ngần"
    cliche = "Nắng vàng long lanh bên thềm đong đầy"
    assert rk._cliche_component(clean) == 0.0
    # 4 cụm sáo ngữ -> -min(1, 0.25*4) = -1.0
    assert rk._cliche_component(cliche) == -1.0


def test_diversity_component():
    rk = _make()
    repetitive = "trời trời trời trời trời trời"
    diverse = "trời thu gió mát trăng ngần"
    # repetitive: 1 bigram distinct / 5 total = 0.2
    assert rk._diversity_component(repetitive) < rk._diversity_component(diverse)


def test_keyword_component():
    poem = "Trời thu gió mát trăng ngần"
    assert LucBatReranker._keyword_component(poem, ["trời", "gió"]) == 1.0   # 2/2 khớp
    assert LucBatReranker._keyword_component(poem, ["mùa xuân"]) == 0.0      # không khớp
    assert LucBatReranker._keyword_component(poem, []) == 0.5                # trung lập


def test_length_component():
    poem = "A\nB\nC"
    assert LucBatReranker._length_component(poem, 3) == 1.0   # đúng số dòng
    assert LucBatReranker._length_component(poem, 4) == 0.0   # lệch 1 -> max(0, 0)  (sai 1 dòng)
    assert LucBatReranker._length_component(poem, 1) == 0.0   # lệch 2 -> âm -> chặn ở 0
    assert LucBatReranker._length_component(poem, None) == 1.0


def test_good_beats_broken():
    # Baseline: bài chuẩn 100 phải thắng bài hỏng (overall 57) với weight mặc định.
    rk = LucBatReranker(evaluator=LucBatEvaluator(), cliches=CLICHES)
    ranked = rk.rerank([KIEU_BROKEN, KIEU_GOOD], metadata={})
    assert len(ranked) == 2
    assert ranked[0]["poem"] == KIEU_GOOD
    assert ranked[1]["poem"] == KIEU_BROKEN
    assert ranked[0]["score"] > ranked[1]["score"]


def test_cliche_penalty_decides_ranking():
    # Hai bài có điểm evaluator bằng nhau (stub 100); bài sạch phải thắng
    # bài nhồi 4 cụm sáo ngữ (cliche -1.0 * 0.15 = -0.15).
    rk = _make()
    clean = "Trời thu gió mát trăng ngần sông vắng"
    cliche = "Nắng vàng long lanh bên thềm đong đầy ngọt ngào"
    ranked = rk.rerank([cliche, clean], metadata={"từ khoá": []})
    assert ranked[0]["poem"] == clean
    assert ranked[0]["components"]["cliche"] > ranked[1]["components"]["cliche"]


def test_weights_defaults_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


# ---- Regression 08/08: evaluator (chất lượng vần) phải thắng keyword ----
# Trước đây evaluator 0.35 (RMA hiệu lực ~10.5%) < keyword 0.20 → bài nhồi keyword
# nhưng vần hỏng bị xếp TRÊN bài hợp vần chuẩn. Sau khi đảo weight (0.50/0.12):
#   KIEU_GOOD  ev 1.00 / kw 0.00 → đứng #1
#   BROKEN_KW  ev 0.59 / kw 1.00 → đứng #2
BROKEN_KW = """chúc ông bà tết sang vui
ông bà chúc tết năm mới thật giàu
chúc ông chúc bà tết vui
chúc tết ông bà may mắn tràn đầy"""


def test_evaluator_dominates_keyword():
    rk = LucBatReranker(evaluator=LucBatEvaluator(), cliches=CLICHES)
    ranked = rk.rerank([BROKEN_KW, KIEU_GOOD],
                       metadata={"từ khoá": ["chúc", "tết", "ông", "bà"], "số câu": 4})
    assert ranked[0]["poem"] == KIEU_GOOD, "Bài hợp vần chuẩn phải thắng bài nhồi keyword"
    assert ranked[0]["components"]["evaluator"] > ranked[1]["components"]["evaluator"]
    # keyword chỉ là tiebreaker: bài #1 vần chuẩn không cần phủ keyword mà vẫn thắng
    assert ranked[0]["components"]["keyword"] < ranked[1]["components"]["keyword"]


def test_old_weights_would_have_flipped():
    # Xác nhận chính regression: với weight cũ (0.35/0.20), bài keyword hỏng vần THẮNG.
    old = {**DEFAULT_WEIGHTS, "evaluator": 0.35, "keyword": 0.20}
    rk_old = LucBatReranker(evaluator=LucBatEvaluator(), cliches=CLICHES, weights=old)
    rk_new = LucBatReranker(evaluator=LucBatEvaluator(), cliches=CLICHES)
    meta = {"từ khoá": ["chúc", "tết", "ông", "bà"], "số câu": 4}
    old_first = rk_old.rerank([BROKEN_KW, KIEU_GOOD], meta)[0]["poem"]
    new_first = rk_new.rerank([BROKEN_KW, KIEU_GOOD], meta)[0]["poem"]
    assert old_first == BROKEN_KW, "Weight cũ phải ưu keyword (tái hiện bug)"
    assert new_first == KIEU_GOOD, "Weight mới phải ưu evaluator (đã fix)"


if __name__ == "__main__":
    print("=== Đang chạy unit tests cho Reranker ===")
    test_cliche_component_penalizes()
    print("✓ test_cliche_component_penalizes: PASSED")
    test_diversity_component()
    print("✓ test_diversity_component: PASSED")
    test_keyword_component()
    print("✓ test_keyword_component: PASSED")
    test_length_component()
    print("✓ test_length_component: PASSED")
    test_good_beats_broken()
    print("✓ test_good_beats_broken: PASSED")
    test_cliche_penalty_decides_ranking()
    print("✓ test_cliche_penalty_decides_ranking: PASSED")
    test_weights_defaults_sum_to_one()
    print("✓ test_weights_defaults_sum_to_one: PASSED")
    print("🎉 Tất cả test trong test_reranker.py đều PASSED 100%!")


def test_lexical_guard_demotes_truncated_keyword():
    broken = "thầy cô vinh dự được người tri â"
    clean = "thầy cô an vui nhận nhiều tri ân"
    guarded = LucBatReranker(evaluator=StubEvaluator(), cliches=CLICHES, lexical_guard=True)
    ranked = guarded.rerank([broken, clean], {"từ khoá": ["hoa đào", "tri ân"]})
    assert ranked[0]["poem"] == clean
    assert ranked[1]["lexical"]["hard_fail"]


def test_lexical_guard_is_off_by_default():
    broken = "thầy cô vinh dự được người tri â"
    reranker = LucBatReranker(evaluator=StubEvaluator(), cliches=CLICHES)
    ranked = reranker.rerank([broken], {"từ khoá": ["tri ân"]})
    assert "lexical" not in ranked[0]
