"""Đánh giá một bài thơ Lục Bát theo cấu trúc, thanh điệu và vần.

SCR kiểm tra cấu trúc toàn bài: chuỗi phải luân phiên Lục 6 và Bát 8, bắt
đầu bằng Lục, kết thúc đủ cặp; có thể kiểm tra thêm expected_num_lines.

TCR đo các vị trí Bằng/Trắc bắt buộc trên những dòng có độ dài chuẩn.
RMA chỉ được tính khi cấu trúc toàn bài hợp lệ và tách thành:
  - exact_rma: tỷ lệ quan hệ vần chính xác;
  - slant_rma: tỷ lệ quan hệ vần thông được chấp nhận;
  - rma: combined_rma = exact_rma + slant_rma.

overall = 0.4 * SCR + 0.3 * TCR + 0.3 * combined RMA.
"""
import string
import unicodedata
from typing import Dict, List, Optional, Tuple

from phonetics import (
    ToneType,
    get_tone,
    is_bang,
    is_trac,
    rhyme_match_kind,
)


_PUNCT = string.punctuation + "“”‘’…–—«»·…"


def clean_syllable(word: str) -> str:
    """NFC, bỏ dấu câu hai bên và lowercase một âm tiết."""
    if not word or not isinstance(word, str):
        return ""
    return unicodedata.normalize("NFC", word.strip()).strip(_PUNCT).lower()


def _line_syllables(line: str) -> List[str]:
    """Tách một dòng thơ thành danh sách âm tiết đã làm sạch."""
    if not line or not isinstance(line, str):
        return []
    return [s for s in (clean_syllable(word) for word in line.split()) if s]


def _is_bang(word: str) -> bool:
    return is_bang(word)


def _is_trac(word: str) -> bool:
    return is_trac(word)


class LucBatEvaluator:
    """Bộ đánh giá Lục Bát có kiểm tra cấu trúc toàn bài."""

    def evaluate(
        self, poem_text: str, expected_num_lines: Optional[int] = None
    ) -> Dict:
        """Đánh giá thơ; expected_num_lines là số dòng bắt buộc nếu prompt quy định."""
        if expected_num_lines is not None:
            if not isinstance(expected_num_lines, int) or expected_num_lines <= 0:
                raise ValueError("expected_num_lines phải là số nguyên dương hoặc None")

        lines = [line for line in poem_text.split("\n") if _line_syllables(line)]
        line_details = [self._analyze_line(line) for line in lines]
        structure = self._analyze_structure(line_details, expected_num_lines)

        scr = self._scr(structure)
        tcr = self._tcr(line_details)
        exact_rma, slant_rma, rma, rhyme_pairs = self._rma(
            lines, structure["structure_ok"]
        )

        overall = 0.4 * scr + 0.3 * tcr + 0.3 * rma
        is_valid = (
            structure["structure_ok"]
            and scr == 100.0
            and tcr == 100.0
            and rma == 100.0
        )

        return {
            "scr": round(scr, 2),
            "tcr": round(tcr, 2),
            "exact_rma": round(exact_rma, 2),
            "slant_rma": round(slant_rma, 2),
            "rma": round(rma, 2),
            "combined_rma": round(rma, 2),
            "overall": round(overall, 2),
            "is_valid_lucbat": is_valid,
            "structure_ok": structure["structure_ok"],
            "structure_errors": structure["errors"],
            "expected_num_lines": expected_num_lines,
            "num_lines": len(lines),
            "lines": line_details,
            "rhyme_pairs": rhyme_pairs,
        }

    def _analyze_line(self, line: str) -> Dict:
        syls = _line_syllables(line)
        n = len(syls)
        correct = 0
        mandatory = 0

        if n == 6:
            for pos, expected in ((1, "B"), (3, "T"), (5, "B")):
                mandatory += 1
                if expected == "B" and _is_bang(syls[pos]):
                    correct += 1
                elif expected == "T" and _is_trac(syls[pos]):
                    correct += 1
        elif n == 8:
            for pos, expected in ((1, "B"), (3, "T"), (5, "B"), (7, "B")):
                mandatory += 1
                if expected == "B":
                    if pos == 7:
                        tone6 = get_tone(syls[5])
                        if tone6 == ToneType.HUYEN:
                            correct += int(get_tone(syls[pos]) == ToneType.NGANG)
                        elif tone6 == ToneType.NGANG:
                            correct += int(get_tone(syls[pos]) == ToneType.HUYEN)
                        else:
                            correct += int(_is_bang(syls[pos]))
                    else:
                        correct += int(_is_bang(syls[pos]))
                elif expected == "T":
                    correct += int(_is_trac(syls[pos]))

        return {
            "text": line,
            "syllables": syls,
            "count": n,
            "is_correct_length": n in (6, 8),
            "correct_positions": correct,
            "mandatory_positions": mandatory,
        }

    def _analyze_structure(
        self, line_details: List[Dict], expected_num_lines: Optional[int]
    ) -> Dict:
        actual_n = len(line_details)
        errors = []
        if actual_n == 0:
            return {
                "structure_ok": False,
                "errors": ["empty_poem"],
                "correct_lines": 0,
                "total_slots": expected_num_lines or 0,
            }

        if actual_n % 2:
            errors.append("incomplete_couplet")
        if expected_num_lines is not None and actual_n != expected_num_lines:
            errors.append("line_count_mismatch")
        if expected_num_lines is not None and expected_num_lines % 2:
            errors.append("odd_expected_num_lines")

        total_slots = max(actual_n, expected_num_lines or actual_n)
        correct_lines = 0
        for index, detail in enumerate(line_details):
            expected_count = 6 if index % 2 == 0 else 8
            within_expected_range = (
                expected_num_lines is None or index < expected_num_lines
            )
            is_complete_slot = not (
                expected_num_lines is None
                and actual_n % 2
                and index == actual_n - 1
            )
            detail["expected_count"] = expected_count
            detail["is_correct_structure_position"] = (
                within_expected_range
                and is_complete_slot
                and detail["count"] == expected_count
            )
            if detail["is_correct_structure_position"]:
                correct_lines += 1
            else:
                errors.append(f"line_{index + 1}_expected_{expected_count}")

        structure_ok = (
            not errors
            and actual_n > 0
            and actual_n % 2 == 0
            and (
                expected_num_lines is None
                or (actual_n == expected_num_lines and expected_num_lines % 2 == 0)
            )
        )
        return {
            "structure_ok": structure_ok,
            "errors": errors,
            "correct_lines": correct_lines,
            "total_slots": total_slots,
        }

    @staticmethod
    def _scr(structure: Dict) -> float:
        total = structure["total_slots"]
        if total == 0:
            return 0.0
        return 100.0 * structure["correct_lines"] / total

    @staticmethod
    def _tcr(line_details: List[Dict]) -> float:
        total = sum(detail["mandatory_positions"] for detail in line_details)
        if total == 0:
            return 0.0
        correct = sum(detail["correct_positions"] for detail in line_details)
        return 100.0 * correct / total

    @staticmethod
    def _rma(
        lines: List[str], structure_ok: bool
    ) -> Tuple[float, float, float, List[Dict]]:
        """Tính vần trên đúng các cặp vị trí, không bỏ dòng sai để ghép lại."""
        if not structure_ok:
            return 0.0, 0.0, 0.0, []

        line_syllables = [_line_syllables(line) for line in lines]
        exact = 0
        slant = 0
        required = 0
        pairs = []

        for couplet_index in range(0, len(line_syllables), 2):
            luc = line_syllables[couplet_index]
            bat = line_syllables[couplet_index + 1]

            kind = rhyme_match_kind(luc[5], bat[5])
            required += 1
            exact += int(kind == "exact")
            slant += int(kind == "slant")
            pairs.append({
                "type": "lung",
                "left": luc[5],
                "right": bat[5],
                "kind": kind or "mismatch",
            })

            if couplet_index + 2 < len(line_syllables):
                next_luc = line_syllables[couplet_index + 2]
                kind = rhyme_match_kind(bat[7], next_luc[5])
                required += 1
                exact += int(kind == "exact")
                slant += int(kind == "slant")
                pairs.append({
                    "type": "chan",
                    "left": bat[7],
                    "right": next_luc[5],
                    "kind": kind or "mismatch",
                })

        if required == 0:
            return 0.0, 0.0, 0.0, pairs

        exact_rma = 100.0 * exact / required
        slant_rma = 100.0 * slant / required
        return exact_rma, slant_rma, exact_rma + slant_rma, pairs
