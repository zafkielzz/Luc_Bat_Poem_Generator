"""Validate và render rhyme scaffold cho Tet4 four-line Lục Bát."""
from __future__ import annotations

from typing import Any

from engine.evaluator import _line_syllables
from phonetics import ToneType, get_tone, is_bang, rhyme_match_kind


SCAFFOLD_KEYS = (
    "line_1_end", "line_2_sixth", "line_2_end", "line_3_end", "line_4_sixth",
)

# Mẫu dự phòng đã qua chính validator: xuân~xuân, nhà~qua, qua~ca.
# Đây là khung âm vị, không phải câu thơ hay output cuối.
DEFAULT_SCAFFOLD = {
    "line_1_end": "xuân",
    "line_2_sixth": "xuân",
    "line_2_end": "nhà",
    "line_3_end": "qua",
    "line_4_sixth": "ca",
}


def validate_scaffold(value: Any) -> dict[str, Any]:
    """Chỉ nhận anchor một âm tiết, đúng thanh và đủ ba quan hệ vần Tet4."""
    if not isinstance(value, dict) or set(value) != set(SCAFFOLD_KEYS):
        return {"valid": False, "reasons": ["invalid_scaffold_schema"]}
    anchors: dict[str, str] = {}
    for key in SCAFFOLD_KEYS:
        candidate = value[key]
        syllables = _line_syllables(candidate) if isinstance(candidate, str) else []
        if len(syllables) != 1:
            return {"valid": False, "reasons": [f"{key}_must_be_one_syllable"]}
        anchors[key] = syllables[0]
    bad_tone = [key for key, syllable in anchors.items() if not is_bang(syllable)]
    if bad_tone:
        return {"valid": False, "reasons": ["anchor_not_bang:" + ",".join(bad_tone)]}
    sixth_tone, end_tone = get_tone(anchors["line_2_sixth"]), get_tone(anchors["line_2_end"])
    if ((sixth_tone == ToneType.HUYEN and end_tone != ToneType.NGANG)
            or (sixth_tone == ToneType.NGANG and end_tone != ToneType.HUYEN)):
        return {"valid": False, "reasons": ["line_2_bang_pair_must_alternate"]}
    pairs = (
        ("line_1_end", "line_2_sixth"),
        ("line_2_end", "line_3_end"),
        ("line_3_end", "line_4_sixth"),
    )
    mismatches = [f"{left}:{right}" for left, right in pairs
                  if rhyme_match_kind(anchors[left], anchors[right]) is None]
    if mismatches:
        return {"valid": False, "reasons": ["rhyme_mismatch:" + ",".join(mismatches)]}
    return {"valid": True, "reasons": [], "anchors": anchors,
            "rhyme_kinds": {f"{left}:{right}": rhyme_match_kind(anchors[left], anchors[right])
                            for left, right in pairs}}


def render_scaffold(scaffold: dict[str, str]) -> str:
    """Ràng buộc vị trí mềm, rõ ràng cho prompt generation."""
    return "\n".join((
        "Khung neo vần đã được validator chấp nhận; ưu tiên giữ đúng các vị trí này:",
        f"- Dòng 1 kết bằng: {scaffold['line_1_end']}",
        f"- Dòng 2: tiếng 6 là {scaffold['line_2_sixth']}; tiếng 8 là {scaffold['line_2_end']}",
        f"- Dòng 3 kết bằng: {scaffold['line_3_end']}",
        f"- Dòng 4: tiếng 6 là {scaffold['line_4_sixth']}",
        "Đừng nhồi anchor nếu làm câu vô nghĩa; ưu tiên diễn đạt tự nhiên và luật Lục Bát.",
    ))


def resolve_scaffold(proposed: Any) -> dict[str, Any]:
    """Tin proposal của Qwen chỉ sau validation; nếu không, dùng fallback có trace."""
    proposal_validation = validate_scaffold(proposed)
    if proposal_validation["valid"]:
        return {"source": "qwen_validated", "scaffold": proposal_validation["anchors"],
                "proposal_validation": proposal_validation}
    fallback_validation = validate_scaffold(DEFAULT_SCAFFOLD)
    assert fallback_validation["valid"], "default rhyme scaffold phải luôn hợp lệ"
    return {"source": "deterministic_fallback", "scaffold": fallback_validation["anchors"],
            "proposal_validation": proposal_validation, "fallback_validation": fallback_validation}
