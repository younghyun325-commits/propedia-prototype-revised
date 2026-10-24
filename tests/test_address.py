from core.address import MSG_EMPTY, MSG_OUT, normalize


def test_a1_a3_same_pnu(con):
    a1 = normalize(con, "강남구 압구정동 527")
    a3 = normalize(con, "서울특별시 강남구 압구정동 527번지")
    assert a1["status"] == a3["status"] == "ok"
    assert a1["pnu"] == a3["pnu"] == "1168011000105270000"
    assert a1["saenghwal"] == "압구정·청담"


def test_input_spacing_variants(con):
    for text in ("강남구압구정동527", "서울 강남구 압구정동 527", " 강남구  압구정동 527 번지 "):
        assert normalize(con, text)["pnu"] == "1168011000105270000"


def test_out_of_scope(con):
    r = normalize(con, "서초구 방배동 818-14")
    assert r["status"] == "out_of_scope"
    assert r["message"] == MSG_OUT
    assert normalize(con, "서울 서초구 반포대로 1")["status"] == "out_of_scope"


def test_not_found_unknown_dong(con):
    r = normalize(con, "강남구 없는동 1")
    assert r["status"] == "not_found"


def test_empty_input(con):
    r = normalize(con, "   ")
    assert r["status"] == "not_found"
    assert r["message"] == MSG_EMPTY


def test_jibun_not_in_demo_list_builds_pnu(con):
    r = normalize(con, "강남구 청담동 1")
    assert r["status"] == "ok"
    assert r["pnu"] == "1168010400100010000"
    assert r["lat"] is None
