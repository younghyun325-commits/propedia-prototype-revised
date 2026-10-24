from core.text import evidence_in, norm, squash_ws


def test_norm_removes_whitespace_and_unifies_dots():
    assert norm("압구정 · 청담\n생활권") == "압구정·청담생활권"
    assert norm("압구정ㆍ청담") == norm("압구정․청담") == norm("압구정‧청담") == norm("압구정・청담") == "압구정·청담"


def test_evidence_in_ignores_spacing_and_newlines():
    page = "가. 공람기간 : 2026. 10. 06. ~ 2026. 11. 06.\n나. 공람장소"
    assert evidence_in("공람기간 : 2026. 10. 06. ~ 2026. 11. 06.", page)
    assert evidence_in("공람기간:2026.10.06.~2026.11.06.", page)
    assert evidence_in("2026. 11. 06.\n나. 공람장소", page)


def test_evidence_in_dot_variants():
    assert evidence_in("압구정ㆍ청담", "지역생활권계획(압구정·청담)")


def test_evidence_in_rejects_short_and_missing():
    assert not evidence_in("가", "가나다")
    assert not evidence_in("", "가나다")
    assert not evidence_in("라마", "가나다")


def test_squash_ws_keeps_dots():
    assert squash_ws("정비구역·정비계획  결정(변경)(안)\n공람·공고") == "정비구역·정비계획 결정(변경)(안) 공람·공고"
