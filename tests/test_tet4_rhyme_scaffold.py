from engine.tet4_rhyme_scaffold import render_scaffold, resolve_scaffold, validate_scaffold


VALID = {
    "line_1_end": "xuân",
    "line_2_sixth": "xuân",
    "line_2_end": "nhà",
    "line_3_end": "qua",
    "line_4_sixth": "ca",
}


def test_valid_scaffold_accepts_slant_and_exact_rhyme_chain():
    result = validate_scaffold(VALID)
    assert result["valid"]
    assert result["rhyme_kinds"]["line_1_end:line_2_sixth"] == "exact"
    assert "Dòng 2: tiếng 6 là xuân" in render_scaffold(VALID)


def test_scaffold_rejects_wrong_rhyme_or_non_bang_anchor():
    invalid = {**VALID, "line_3_end": "mắt"}
    assert not validate_scaffold(invalid)["valid"]
    invalid = {**VALID, "line_2_end": "mắt"}
    assert "anchor_not_bang" in validate_scaffold(invalid)["reasons"][0]


def test_invalid_qwen_proposal_uses_a_valid_deterministic_fallback():
    proposed = {**VALID, "line_3_end": "vui"}
    resolved = resolve_scaffold(proposed)
    assert resolved["source"] == "deterministic_fallback"
    assert validate_scaffold(resolved["scaffold"])["valid"]
