"""N-best reranker cho thơ Lục Bát.

Evaluator là thành phần chính; diversity/cliché/keyword/length chỉ đóng vai trò
điều chỉnh. Khi metadata có số câu, evaluator nhận expected_num_lines để ranking
không vô tình ưu tiên bài sai số dòng.
"""
from typing import Dict, List, Optional

from engine.evaluator import LucBatEvaluator, _line_syllables
from engine.collocation import CollocationScorer
from engine.lexical_guard import assess as assess_lexical


DEFAULT_WEIGHTS = {
    "evaluator": 0.80,
    "diversity": 0.05,
    "cliche": 0.10,
    "keyword": 0.03,
    "length": 0.02,
}

CLICHE_PENALTY_PER_HIT = 0.25


class LucBatReranker:
    """Chấm điểm và xếp hạng các ứng viên Lục Bát."""

    def __init__(
        self,
        evaluator: LucBatEvaluator,
        cliches: List[str],
        weights: Optional[Dict[str, float]] = None,
        collocation_scorer: Optional[CollocationScorer] = None,
        lexical_guard: bool = False,
    ):
        self.evaluator = evaluator
        self.cliches = [c.strip().lower() for c in cliches if c.strip()]
        self.weights = weights if weights else dict(DEFAULT_WEIGHTS)
        self.collocation_scorer = collocation_scorer
        self.lexical_guard = lexical_guard

    def _evaluate(self, poem: str, target_lines: Optional[int]) -> Dict:
        """Gọi evaluator với contract mới, vẫn tương thích test stub cũ."""
        if target_lines is None:
            return self.evaluator.evaluate(poem)
        try:
            return self.evaluator.evaluate(
                poem, expected_num_lines=target_lines
            )
        except TypeError as exc:
            if "expected_num_lines" not in str(exc):
                raise
            return self.evaluator.evaluate(poem)

    @staticmethod
    def _evaluator_component(evaluation: Dict) -> float:
        return max(0.0, min(1.0, evaluation["overall"] / 100.0))

    def _diversity_component(self, poem: str) -> float:
        """distinct bigrams / total bigrams trên toàn bài."""
        syls = []
        for line in poem.split("\n"):
            syls.extend(_line_syllables(line))
        if len(syls) < 2:
            return 0.0
        bigrams = list(zip(syls, syls[1:]))
        return len(set(bigrams)) / len(bigrams)

    def _cliche_component(self, poem: str) -> float:
        """Penalty âm trong [-1, 0]."""
        text = poem.lower()
        count = sum(1 for cliche in self.cliches if cliche and cliche in text)
        return -min(1.0, CLICHE_PENALTY_PER_HIT * count)

    @staticmethod
    def _keyword_component(poem: str, keywords: List[str]) -> float:
        if not keywords:
            return 0.5
        poem_syls = set()
        for line in poem.split("\n"):
            poem_syls.update(_line_syllables(line))
        matched = 0
        for keyword in keywords:
            parts = _line_syllables(keyword)
            if parts and all(part in poem_syls for part in parts):
                matched += 1
        return matched / len(keywords)

    @staticmethod
    def _length_component(poem: str, target_lines: Optional[int]) -> float:
        if not target_lines or target_lines <= 0:
            return 1.0
        actual = len([line for line in poem.split("\n") if _line_syllables(line)])
        return max(0.0, 1.0 - abs(actual - target_lines))

    def score(self, poem: str, metadata: Dict) -> Dict:
        """Chấm một bài, trả về component breakdown và evaluator output duy nhất."""
        keywords = metadata.get("từ khoá") or metadata.get("keywords") or []
        target_lines = metadata.get("số câu") or metadata.get("num_lines")
        evaluation = self._evaluate(poem, target_lines)

        components = {
            "evaluator": self._evaluator_component(evaluation),
            "diversity": self._diversity_component(poem),
            "cliche": self._cliche_component(poem),
            "keyword": self._keyword_component(poem, keywords),
            "length": self._length_component(poem, target_lines),
        }
        if self.collocation_scorer is not None:
            components["collocation"] = self.collocation_scorer.score(poem)
        total = sum(
            self.weights.get(name, 0.0) * value
            for name, value in components.items()
        )
        result = {
            "score": round(total, 4),
            "components": components,
            "eval": evaluation,
        }
        if self.lexical_guard:
            result["lexical"] = assess_lexical(poem, keywords)
        return result

    def rerank(self, candidates: List[str], metadata: Dict) -> List[Dict]:
        """Xếp hạng giảm dần; lexical guard chỉ loại các lỗi chắc chắn."""
        scored = [{"poem": poem, **self.score(poem, metadata)} for poem in candidates]
        if self.lexical_guard:
            scored.sort(key=lambda item: (item["lexical"]["hard_fail"], -item["score"]))
        else:
            scored.sort(key=lambda item: item["score"], reverse=True)
        return scored
