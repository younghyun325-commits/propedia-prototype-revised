"""건축물대장 요약 (feedback.md §5-1): PNU → 요청값, 요약 형식, 미조회 안내."""
import json
from pathlib import Path

import pytest

from core.lookup import building
from pipeline.fetch_buildings import NOT_FOUND, request_params, summarize

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_KEYS = {"pnu", "found", "fetched_at", "source", "main_count", "bld_names", "main_purpose", "structure",
                "use_apr_day", "max_grnd_flr", "max_ugrnd_flr", "total_hhld", "total_area", "zoning", "note",
                "detail_purposes"}


def test_request_params_general_and_san():
    assert request_params("1168011000105270000") == {"sigunguCd": "11680", "bjdongCd": "11000", "platGbCd": "0",
                                                     "bun": "0527", "ji": "0000"}
    assert request_params("1168010400101340038")["ji"] == "0038"
    assert request_params("1168011000205270001")["platGbCd"] == "1"     # 산


def test_summarize_main_buildings_only():
    items = [
        {"mainAtchGbCdNm": "주건축물", "bldNm": "한양아파트", "mainPurpsCdNm": "공동주택", "strctCdNm": "철근콘크리트구조",
         "useAprDay": "19800515", "grndFlrCnt": "12", "ugrndFlrCnt": "0", "hhldCnt": "120", "totArea": "10000.5",
         "jiyukCdNm": "제3종일반주거지역", "jiguCdNm": "아파트지구", "guyukCdNm": ""},
        {"mainAtchGbCdNm": "주건축물", "bldNm": "한양아파트", "mainPurpsCdNm": "공동주택", "strctCdNm": "철근콘크리트구조",
         "useAprDay": "19790101", "grndFlrCnt": "13", "ugrndFlrCnt": "1", "hhldCnt": "119", "totArea": "9000"},
        {"mainAtchGbCdNm": "부속건축물", "bldNm": "경비실", "mainPurpsCdNm": "제1종근린생활시설", "grndFlrCnt": "1",
         "hhldCnt": "0", "totArea": "20"},
    ]
    s = summarize("1168011000105280000", items, [], "2026-10-26")
    assert set(s) == SUMMARY_KEYS and s["found"] is True
    assert s["main_count"] == 2 and s["bld_names"] == ["한양아파트"]
    assert s["use_apr_day"] == "1979-01-01" and s["max_grnd_flr"] == 13 and s["max_ugrnd_flr"] == 1
    assert s["total_hhld"] == 239 and s["total_area"] == 19000.5
    assert s["zoning"] == {"jiyuk": "제3종일반주거지역", "jigu": "아파트지구", "guyuk": None}
    assert s["detail_purposes"] == ["공동주택"]


def test_summarize_zoning_from_basis_when_title_has_none():
    title = [{"mainAtchGbCdNm": "주건축물", "bldNm": "A"}]
    basis = [{"jiyukCdNm": "일반상업지역", "jiguCdNm": "", "guyukCdNm": ""}]
    assert summarize("1168010100107370000", title, basis, "2026-10-26")["zoning"]["jiyuk"] == "일반상업지역"


def test_summarize_not_found():
    s = summarize("1168011000105270000", [], [], "2026-10-26")
    assert s == {"pnu": "1168011000105270000", "found": False, "note": NOT_FOUND, "fetched_at": "2026-10-26"}
    assert "조회되지 않았습니다" in NOT_FOUND


def test_lookup_building_not_fetched(con):
    b, note = building(con, "1168010800101000000")      # 시연 주소가 아닌 논현동 100
    assert b is None and "조회하지 않았습니다" in note


def test_seed_buildings_format():
    path = ROOT / "seed" / "buildings.json"
    if not path.exists():
        pytest.skip("seed/buildings.json 없음 — python -m pipeline.fetch_buildings 실행 전 (HUMAN_TODO)")
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert rows and len({r["pnu"] for r in rows}) == len(rows)
    for r in rows:
        assert r["fetched_at"] and len(r["pnu"]) == 19
        assert set(r) in (SUMMARY_KEYS, SUMMARY_KEYS - {"detail_purposes"}) if r["found"] else set(r) == {"pnu", "found", "note", "fetched_at"}
