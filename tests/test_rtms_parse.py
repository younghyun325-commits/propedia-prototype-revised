"""실거래가 상세 응답 파싱 (docs/map/PLAN.md P17 2-1). 네트워크 없음 — 1단계 견본 tests/fixtures/rtms/."""
from pathlib import Path

import pytest

from pipeline import rtms_parse as rp

FIX = Path(__file__).parent / "fixtures" / "rtms" / "trade_202610_p1.xml"


def item(**kw) -> dict:
    base = {"sggCd": "11680", "umdCd": "10600", "landCd": "1", "bonbun": "0316", "bubun": "0000", "aptSeq": "11680-218",
            "aptNm": "은마", "umdNm": "대치동", "jibun": "316", "aptDong": None, "excluUseAr": "76.79",
            "dealYear": "2026", "dealMonth": "10", "dealDay": "16", "dealAmount": "319,000", "floor": "7",
            "buildYear": "1979", "dealingGbn": "중개거래", "landLeaseholdGbn": "N", "cdealType": None, "cdealDay": None,
            "rgstDate": None}
    return base | kw


def test_amount_and_contract_date():
    assert rp.amount("319,000") == 319000
    assert rp.amount(" 50,000 ") == 50000
    assert rp.amount(None) is None and rp.amount("") is None
    assert rp.ymd("2026", "1", "5") == "2026-01-05"
    r = rp.record(item())
    assert r["amount_10k_won"] == 319000 and r["contract_date"] == "2026-10-16"


def test_cancel_two_digit_year_and_registered_date():
    r = rp.record(item(cdealType="O", cdealDay="26.11.03", rgstDate="26.11.20"))
    assert r["is_cancelled"] == 1 and r["cancelled_date"] == "2026-11-03"
    assert r["registered_date"] == "2026-11-20"
    r2 = rp.record(item())
    assert r2["is_cancelled"] == 0 and r2["cancelled_date"] is None and r2["registered_date"] is None
    assert rp.short_date("16.01.09") == "2016-01-09"


def test_pnu_digits():
    assert rp.pnu("11680", "10600", "1", "0316", "0000") == ("1168010600103160000", None)
    assert rp.pnu("11680", "10600", "2", "12", "3")[0] == "1168010600200120003"       # 산 지번, 4자리로 채움
    for args, why in [(("11680", "1060", "1", "0316", "0000"), "자리 수"),
                      (("11680", "10600", "1", "12345", "0"), "자리 수"),
                      (("11680", None, "1", "0316", "0000"), "없음"),
                      (("11680", "10600", "1", "03a6", "0000"), "숫자 아님"),
                      (("11680", "10600", "3", "0316", "0000"), "landCd")]:
        p, reason = rp.pnu(*args)
        assert p is None and why in reason
    r = rp.record(item(umdCd="106"))
    assert r["pnu"] is None and "자리 수" in r["pnu_reason"]


def test_negative_floor_and_area():
    r = rp.record(item(floor="-1", excluUseAr="84.9712"))
    assert r["floor"] == -1 and r["exclusive_area_m2"] == 84.97


def test_raw_hash_fixed_and_drops_personal_fields():
    a = rp.record(item())
    b = rp.record(item(buyerGbn="개인", slerGbn="법인", estateAgentSggNm="서울 강남구"))
    assert a["raw_hash"] == b["raw_hash"]                  # 개인 정보 성격 필드는 해시·저장에 없음
    assert not rp.DROP_FIELDS & set(b)
    assert rp.record(item(floor="8"))["raw_hash"] != a["raw_hash"]
    assert len(a["raw_hash"]) == 64


def test_number_same_in_month():
    recs = [rp.record(item()), rp.record(item()), rp.record(item()), rp.record(item(floor="3"))]
    n = rp.number_same(recs)
    assert n == 2 and len({r["raw_hash"] for r in recs}) == 4
    again = [rp.record(item()), rp.record(item()), rp.record(item()), rp.record(item(floor="3"))]
    rp.number_same(again)
    assert [r["raw_hash"] for r in again] == [r["raw_hash"] for r in recs]   # 순서와 상관없이 같은 해시


def test_parse_fixture_and_head():
    head, items = rp.parse_xml(FIX.read_text(encoding="utf-8"))
    rp.check_head(head)
    assert head["totalCount"] and len(items) == 10
    assert all(not rp.DROP_FIELDS & set(it) for it in items)
    recs = [rp.record(it) for it in items]
    assert all(r["pnu"] and len(r["pnu"]) == 19 for r in recs)
    assert any(r["is_cancelled"] for r in recs)


@pytest.mark.parametrize("code", ["22", "99", "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"])
def test_bad_result_code(code):
    with pytest.raises(rp.RtmsError):
        rp.check_head({"resultCode": code, "resultMsg": "한도 초과"})
