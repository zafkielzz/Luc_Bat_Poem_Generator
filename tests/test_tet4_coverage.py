from engine.tet4_coverage import (
    coverage_instruction, evaluate_coverage, evaluate_acceptance,
    extract_recipients, retry_feedback,
)


def test_content_phrase_is_not_misread_as_second_recipient():
    assert extract_recipients(
        "Chúc ông bà năm mới bình an, con cháu sum vầy"
    ) == ["ông bà"]
    assert extract_recipients("Chúc con cháu học hành tiến bộ") == ["con cháu"]


def test_paraphrase_counts_semantically_but_not_as_exact_keyword():
    poem = "Ông bà vui đón mùa xuân\nCháu con quây quần bên sân mái nhà"
    report = evaluate_coverage(
        poem, "Chúc ông bà bình an, con cháu sum vầy",
        ["con cháu", "sum vầy", "lộc xuân"],
    )
    assert report["recipient_pass"]
    assert report["semantic_keyword_count"] == 2
    assert report["exact_keyword_count"] == 0
    assert not report["pass"]
    assert "no_exact_keyword" in report["reasons"]


def test_one_exact_plus_one_paraphrase_passes_content_gate():
    poem = "Ông bà vui đón mùa xuân\nCon cháu quây quần bên sân mái nhà"
    report = evaluate_coverage(
        poem, "Chúc ông bà bình an, con cháu sum vầy",
        ["con cháu", "sum vầy", "lộc xuân"],
    )
    assert report["pass"]
    assert report["exact_keyword_count"] == 1
    assert report["semantic_keyword_count"] == 2


def test_missing_recipient_is_a_hard_content_failure():
    poem = "Trẻ con sum vầy mùa xuân\nLộc xuân rạng rỡ ngoài sân mái nhà"
    report = evaluate_coverage(
        poem, "Chúc ông bà bình an", ["con cháu", "sum vầy", "lộc xuân"])
    assert not report["pass"]
    assert "missing_recipient" in report["reasons"]


def test_acceptance_keeps_form_separate_from_content():
    item = {
        "poem": "Ông bà vui đón mùa xuân\nCon cháu quây quần bên sân mái nhà",
        "eval": {"scr": 100, "tcr": 100, "combined_rma": 66.67},
        "lexical": {"hard_fail": False},
    }
    result = evaluate_acceptance(item, {
        "ý chúc": "Chúc ông bà bình an", "từ khoá": ["con cháu", "sum vầy", "lộc xuân"]})
    assert result["coverage"]["pass"]
    assert not result["form_pass"]
    assert not result["pass"]


def test_initial_contract_and_retry_keep_content_without_keyword_stuffing():
    metadata = {"ý chúc": "Chúc ông bà bình an", "từ khoá": ["con cháu", "sum vầy", "lộc xuân"]}
    contract = coverage_instruction(metadata)
    assert "ông bà" in contract and "ít nhất một" in contract and "2/3" in contract
    feedback = retry_feedback([{
        "coverage": {"pass": True}, "form_pass": False,
    }], metadata)
    assert "giữ nguyên coverage" in feedback
    assert "đừng nhồi thêm" in feedback
    assert "ba liên kết vần" in feedback
