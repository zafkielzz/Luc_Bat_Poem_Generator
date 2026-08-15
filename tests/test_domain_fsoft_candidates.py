from scripts.build_domain_fsoft_candidates import is_domain_record


def test_keeps_direct_tet_signal():
    keep, signals = is_domain_record("Tết về bên bếp bánh chưng xanh")
    assert keep
    assert signals == ["tet_direct"]


def test_requires_reunion_for_generic_spring():
    assert not is_domain_record("Xuân qua ngày cũ lặng im")[0]
    assert is_domain_record("Xuân về gia đình quây quần bên nhau")[0]


def test_does_not_match_mai_as_time_word():
    assert not is_domain_record("Ngày mai ta lại lên đường")[0]
