"""저장 응답(tests/fixtures)으로 실시간 호출을 흉내 내는 fetch (feedback2.md §2-3). 네트워크를 쓰지 않는다.

fixtures는 pipeline/check_keys.py가 L0 점검 때 실제 호출로 받아 두었다 (키가 없는지 검사함).
"""
import json
from pathlib import Path

from core.live.http import LiveError

F = Path(__file__).resolve().parent / "fixtures"

JUSO = {
    "서울특별시 강남구 테헤란로 427": "teheran_427.json",
    "테헤란로 427": "teheran_427.json",
    "강남구 도곡로": "ambiguous_dogok_ro.json",
    "방배중앙로13길 26": "out_of_scope_seocho.json",
    "아무말대잔치길 99999": "empty.json",
    "테헤란로 427 키오류": "error_bad_key.json",
    "테헤란로 427 전부실패": "error_bad_key.json",
}
COORD = {
    "서울특별시 강남구 일원동 619": "getcoord_1168011400106190000.json",
    "서울특별시 강남구 압구정동 527": "getcoord_527.json",
}

# 필지 점 조회 저장 응답 (pipeline/check_keys.py --parcel-at). geomFilter 문자열 → 파일
PARCEL_AT = {
    "POINT(127.031577 37.498701)": "parcel_at_1168010100108230000.json",     # 역삼동 823
    "POINT(127.084139 37.493922)": "parcel_at_daecheong.json",               # 일원동 629-8 (대청마을 안)
    "POINT(127.0325 37.4837)": "parcel_at_outside.json",                     # 서초구
}
PARCEL_BY_PNU = {
    "pnu:=:1168010100108230000": "parcel_at_1168010100108230000.json",
    "pnu:=:1168011400106290008": "parcel_at_daecheong.json",
}


def load(*parts) -> dict:
    return json.loads(F.joinpath(*parts).read_text(encoding="utf-8"))


class FixtureFetch:
    """fetch(url, params) 대체. calls에 호출 기록을 남긴다. fail_all이면 모든 호출이 실패한다."""

    def __init__(self, fail_all: bool = False, fail_vworld_search: bool = False):
        self.calls = []
        self.fail_all = fail_all
        self.fail_vworld_search = fail_vworld_search

    def __call__(self, url: str, params: dict) -> dict:
        self.calls.append((url, dict(params)))
        if self.fail_all:
            raise LiveError("TimeoutError")
        if "addrlink" in url:
            name = JUSO.get(params["keyword"], "empty.json")
            return load("juso", name)
        if url.endswith("/req/search"):
            if self.fail_vworld_search or params["query"].endswith("전부실패"):
                raise LiveError("TimeoutError")
            return load("vworld", "search_road_teheran_427.json")
        if url.endswith("/req/data"):          # 2D 데이터 연속지적도 (P15 필지 클릭)
            if "geomFilter" in params:
                name = PARCEL_AT.get(params["geomFilter"], "parcel_at_notfound.json")
            else:
                name = PARCEL_BY_PNU.get(params.get("attrFilter", ""), "parcel_at_notfound.json")
            return load("vworld", name)
        if url.endswith("/req/address"):
            return load("vworld", COORD.get(params["address"], "getcoord_notfound.json"))
        op = url.rsplit("/", 1)[-1]
        pnu = params["pnu"]
        p = F / "vworld" / f"{op}_{pnu}.json"
        if p.exists():
            return load("vworld", p.name)
        nodata = F / "vworld" / f"{op}_nodata.json"
        return load("vworld", nodata.name if nodata.exists() else "getLandUseAttr_nodata.json")
