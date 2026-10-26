"""도로명주소 실시간 검색과 대체 경로 (저장 응답, 네트워크 없음) — feedback2.md §3-1, §8-3."""
import pytest

from core.address import normalize
from core.live import juso, vworld
from core.live.http import LiveError
from core.lookup import lookup
from core import live as live_mod
from live_fixtures import FixtureFetch, load


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("JUSO_CONFM_KEY", "test-juso")
    monkeypatch.setenv("JUSO_CONFM_KEY_ALT", "")
    monkeypatch.setenv("VWORLD_API_KEY", "test-key")
    juso._cache.clear()
    vworld._land_cache.clear()
    yield
    juso._cache.clear()
    vworld._land_cache.clear()


def search_with(fetch):
    return lambda q: juso.search(q, fetch=fetch)


def test_parse_single_result():
    res = juso.parse_juso(load("juso", "teheran_427.json"))
    assert res["status"] == "ok" and len(res["results"]) == 1
    r = res["results"][0]
    assert r["pnu"] == "1168010500101430040" and r["sgg_name"] == "강남구"
    assert r["road_address"] == "서울특별시 강남구 테헤란로 427"


def test_parse_empty_and_error():
    assert juso.parse_juso(load("juso", "empty.json"))["status"] == "empty"
    err = juso.parse_juso(load("juso", "error_bad_key.json"))
    assert err["status"] == "error" and err["error_code"] == "E0001"


def test_road_address_to_pnu(con):
    n = normalize(con, "서울특별시 강남구 테헤란로 427", search=search_with(FixtureFetch()))
    assert n["status"] == "ok" and n["pnu"] == "1168010500101430040" and n["match_via"] == "juso"
    assert n["dong_name"] == "삼성동" and n["jibun_address"] == "서울특별시 강남구 삼성동 143-40"


def test_ambiguous_candidates(con):
    n = normalize(con, "강남구 도곡로", search=search_with(FixtureFetch()))
    assert n["status"] == "ambiguous" and 2 <= len(n["candidates"]) <= 5
    assert all(c["pnu"].startswith("11680") and c["jibun_address"] for c in n["candidates"])


def test_out_of_scope_from_search(con):
    n = normalize(con, "방배중앙로13길 26", search=search_with(FixtureFetch()))
    assert n["status"] == "out_of_scope"


def test_no_result(con):
    n = normalize(con, "아무말대잔치길 99999", search=search_with(FixtureFetch()))
    assert n["status"] == "not_found" and "찾지 못했습니다" in n["message"]


def test_juso_failure_falls_back_to_vworld_search(con):
    n = normalize(con, "테헤란로 427 키오류", search=search_with(FixtureFetch()))
    assert n["status"] == "ok" and n["match_via"] == "vworld-search" and n["pnu"] == "1168010500101430040"


def test_both_fail_shows_guidance(con):
    n = normalize(con, "테헤란로 427 전부실패", search=search_with(FixtureFetch()))
    assert n["status"] == "not_found" and n["message"].startswith("도로명주소 검색을 지금 쓸 수 없습니다")


def test_timeout_shows_guidance(con):
    n = normalize(con, "서울특별시 강남구 테헤란로 427", search=search_with(FixtureFetch(fail_all=True)))
    assert n["status"] == "not_found" and "지번 주소" in n["message"]


def test_demo_and_jibun_need_no_network(con):
    f = FixtureFetch()
    for text in ("강남구 일원동 619", "서울특별시 강남구 개포로120길 55", "강남구 논현동 100"):
        assert normalize(con, text, search=search_with(f))["status"] == "ok"
    assert f.calls == []


def test_lookup_live_road_address_does_not_break(con):
    """시연 목록 밖 도로명 → 실시간 검색 → 토지 정보(저장 응답에 그 필지가 없어 '없음' 안내). 화면이 깨지지 않는다."""
    r = lookup(con, "서울특별시 강남구 테헤란로 427", live=live_mod.Live(fetch=FixtureFetch()))
    assert r["status"] == "ok" and r["normalized"]["pnu"] == "1168010500101430040"
    land = r["layers"]["parcel"]["land"]
    assert land["status"] == "unavailable" and land["note"]
    assert r["layers"]["city"] and r["layers"]["gu"]["items"]


def test_lookup_ambiguous_has_candidates(con):
    r = lookup(con, "강남구 도곡로", live=live_mod.Live(fetch=FixtureFetch()))
    assert r["status"] == "ambiguous" and r["layers"] is None and r["candidates"]


def test_live_error_type_has_no_url():
    e = LiveError("TimeoutError")
    assert "http" not in str(e)
