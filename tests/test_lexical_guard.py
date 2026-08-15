from engine.lexical_guard import assess


def test_orphan_vowel_is_hard_failure():
    result = assess("thầy cô vinh dự được người tri â", ["hoa đào", "tri ân"])
    assert result["hard_fail"]
    assert {issue["type"] for issue in result["issues"]} == {"orphan_vowel", "truncated_keyword"}


def test_complete_keyword_has_no_failure():
    result = assess("thầy cô an vui nhận nhiều tri ân", ["hoa đào", "tri ân"])
    assert not result["hard_fail"]


def test_rare_but_complete_word_is_not_guessed_as_error():
    result = assess("mùa xuân rạng rỡ ngát hương", ["mùa xuân", "hương"])
    assert not result["hard_fail"]
