from scripts.import_tet4_gold_review_v2 import (
    build_prompt,
    clean_poem_for_training,
    parse_keywords,
)


def test_clean_poem_keeps_words_and_removes_decorative_wrappers():
    raw = 'Câu "thơ" (đầu)*\n( No ba ngày tết đói ba tháng hè)*'
    assert clean_poem_for_training(raw) == "Câu thơ đầu\nNo ba ngày tết đói ba tháng hè"


def test_parse_keywords_requires_two_or_three_unique_values():
    assert parse_keywords("sum vầy | phúc | học giỏi") == ["sum vầy", "phúc", "học giỏi"]
    try:
        parse_keywords("sum vầy | sum vầy")
    except ValueError as error:
        assert "không trùng" in str(error)
    else:
        raise AssertionError("duplicate keywords must fail")


def test_prompt_is_derived_without_prompt_draft():
    assert build_prompt("cha mẹ", ["sức khỏe", "an vui"], "Chân thành") == (
        "Viết một bài thơ Lục Bát 4 dòng để chúc Tết cho cha mẹ. "
        "Dùng tự nhiên các từ khóa: sức khỏe, an vui. Giọng: Chân thành."
    )



def test_unspecified_recipient_is_canonicalized_to_moi_nha():
    assert build_prompt("chung chung", ["bình an", "an vui"], "Chân thành") == (
        "Viết một bài thơ Lục Bát 4 dòng để chúc Tết cho mọi nhà. "
        "Dùng tự nhiên các từ khóa: bình an, an vui. Giọng: Chân thành."
    )
