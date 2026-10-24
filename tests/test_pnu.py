from core.address import make_pnu, parse_jibun, pnu_from_juso


def test_make_pnu_basic():
    assert make_pnu("1168011000", 527) == "1168011000105270000"


def test_make_pnu_sub_and_san():
    assert make_pnu("1168010700", 649, 9) == "1168010700106490009"
    assert make_pnu("1168010100", 12, 3, san=True) == "1168010100200120003"


def test_apgujeong_527():
    j = parse_jibun("강남구 압구정동 527")
    assert j == {"gu": "강남구", "dong": "압구정동", "san": False, "main": 527, "sub": 0}
    assert make_pnu("1168011000", j["main"], j["sub"], j["san"]) == "1168011000105270000"


def test_parse_jibun_variants():
    assert parse_jibun("서울특별시 강남구 압구정동 527번지")["main"] == 527
    assert parse_jibun("서울 강남구 신사동 649-9")["sub"] == 9
    assert parse_jibun("강남구 역삼동 산 12")["san"] is True
    assert parse_jibun("테헤란로 152") is None


def test_pnu_from_juso():
    row = {"admCd": "1168011000", "mtYn": "0", "lnbrMnnm": "527", "lnbrSlno": "0"}
    assert pnu_from_juso(row) == "1168011000105270000"
    assert pnu_from_juso({**row, "mtYn": "1"}) == "1168011000205270000"
