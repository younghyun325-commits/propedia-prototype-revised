"""P18 생활 인프라 빌드 (pipeline/fetch_pois.py) — 네트워크 없음.

- 순수 함수: 견본(tests/fixtures/sdsc, 작은 CSV 행)으로 분류표 적용·강남구 밖 제외·역 합치기·학교 운영 필터·노선 연결
- 빌드 결과(public/data/layers): 정류장 좌표 300m 검증 6곳(D2), 같은 이름 정류장 따로, 가상·선착장 제외, 노선 순번,
  manifest 라이선스·기준일 메모, 저장 파일 키 없음, M24
- 원본 CSV(data_raw/12.생활인프라)는 커밋하지 않으므로, 원본이 필요한 검사는 파일이 없으면 건너뛴다
"""
import json
import os
from pathlib import Path

import pytest

from pipeline import fetch_pois as fp

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ROOT / "public" / "data" / "layers"
FIX = ROOT / "tests" / "fixtures" / "sdsc" / "storeListInDong_p1.json"
NO_ZONES: list = []
IN = lambda lon, lat, m: True  # noqa: E731  (경계 판정 대신)


def layer(name: str) -> list[dict]:
    return json.loads((LAYERS / name).read_text(encoding="utf-8"))["features"]


# ---------- 상가 (편의시설) ----------
def test_store_fixture_has_no_key_and_parses():
    text = FIX.read_text(encoding="utf-8")
    assert "serviceKey" not in text and "ServiceKey" not in text
    items = fp.store_items(json.loads(text))
    assert len(items) == 7 and {"bizesId", "indsSclsCd", "lon", "lat", "signguCd"} <= set(items[0])


def test_poi_categories_applied_excluded_and_outside_dropped():
    codes, cats = fp.load_categories()
    assert list(cats) == ["supermarket", "convenience", "clinic", "pharmacy", "cafe", "academy"]
    assert cats["clinic"]["sub_categories"] == ["병원", "의원", "치과", "한방"]
    feats, rep = fp.poi_features(fp.store_items(json.loads(FIX.read_text(encoding="utf-8"))), codes, NO_ZONES, "202609")
    by = {f["properties"]["category_code"]: f["properties"] for f in feats}
    assert set(by) == {"I21201", "Q10210", "G20405", "Q10211"}           # 요가/필라테스(P10603)는 표에 없음
    assert by["Q10210"]["category"] == "clinic" and by["Q10210"]["sub_category"] == "치과"
    assert by["Q10211"]["sub_category"] == "한방"
    assert "sub_category" not in by["I21201"]
    assert by["G20405"]["name"].endswith(" 견본점")                        # 상호명 + 지점명
    assert rep["excluded"] == {"분류표에 없는 업종": 1, "좌표 없음": 1, "강남구 밖 (시군구 코드)": 1}
    p = by["I21201"]
    assert set(p) == {"id", "kind", "name", "category", "category_code", "address", "as_of", "lon", "lat",
                      "within_impact", "impact_buffer_m"}                  # 층·건물명 등은 넣지 않음
    assert p["id"].startswith("poi:") and p["as_of"] == "202609"


def test_excluded_categories_listed_in_seed():
    import yaml
    y = yaml.safe_load((ROOT / "seed" / "poi_categories.yaml").read_text(encoding="utf-8"))
    assert y["status"] == "confirmed"
    ex = {e["code"] for e in y["excluded"]}
    assert {"Q10402", "M11101", "R10202", "P10603", "P10625", "P10617", "P10623", "G20509"} == ex
    assert any(m["label"] == "은행" for m in y["missing"])
    assert y["categories"][0]["label"] == "슈퍼마켓" and "대형마트" in y["categories"][0]["note"]


# ---------- 학교 ----------
def test_school_operating_filter_and_gangnam_only():
    rows = [
        {"학교ID": "S1", "학교명": "가", "학교급구분": "초등학교", "운영상태": "운영", "소재지도로명주소": "서울특별시 강남구 A로 1",
         "소재지지번주소": "", "위도": "37.5", "경도": "127.05", "데이터기준일자": "2026-10-01"},
        {"학교ID": "S2", "학교명": "나", "학교급구분": "중학교", "운영상태": "휴교", "소재지도로명주소": "서울특별시 강남구 B로 2",
         "소재지지번주소": "", "위도": "37.5", "경도": "127.05", "데이터기준일자": "2026-10-01"},
        {"학교ID": "S3", "학교명": "다", "학교급구분": "고등학교", "운영상태": "운영", "소재지도로명주소": "서울특별시 서초구 C로 3",
         "소재지지번주소": "", "위도": "37.5", "경도": "127.0", "데이터기준일자": "2026-10-01"},
    ]
    feats, rep = fp.school_features(rows, NO_ZONES)
    assert [f["id"] for f in feats] == ["school:S1"]
    assert rep["raw_gangnam"] == 2 and rep["excluded"] == {"운영상태 '휴교'": 1}
    assert feats[0]["properties"]["level"] == "초등학교" and feats[0]["properties"]["as_of"] == "2026-10-01"


# ---------- 지하철역 ----------
def test_station_merge_rule_paren_and_300m():
    rows = [
        {"역사_ID": "9006", "역사명": "삼성", "호선": "수도권 광역급행철도", "위도": "37.50887", "경도": "127.06324"},
        {"역사_ID": "0219", "역사명": "삼성(무역센터)", "호선": "2호선", "위도": "37.50881", "경도": "127.06316"},
        {"역사_ID": "0222", "역사명": "강남", "호선": "2호선", "위도": "37.49794", "경도": "127.02760"},
        {"역사_ID": "D7", "역사명": "강남", "호선": "신분당선", "위도": "37.49680", "경도": "127.02860"},
        {"역사_ID": "X1", "역사명": "먼곳(가)", "호선": "1호선", "위도": "37.50", "경도": "127.00"},
        {"역사_ID": "X2", "역사명": "먼곳", "호선": "2호선", "위도": "37.52", "경도": "127.00"},   # 2km 떨어짐 → 안 합침
    ]
    st, merged, apart = fp.merge_stations(rows)
    by = {s["name"]: s for s in st if s["name"] != "먼곳"}
    assert by["삼성"]["aliases"] == ["삼성", "삼성(무역센터)"] and by["삼성"]["lines"] == ["2호선", "수도권 광역급행철도"]
    # 위치 = 호선이 가장 많은 원자료 이름의 행 (같으면 이름 순 → '삼성' 행), 평균 아님
    assert (by["삼성"]["lon"], by["삼성"]["lat"]) == (127.06324, 37.50887) and by["삼성"]["anchor_id"] == "9006"
    assert by["강남"]["lines"] == ["2호선", "신분당선"] and by["강남"]["aliases"] == ["강남"]
    assert [m["name"] for m in merged] == ["삼성"]
    assert apart == [{"name": "먼곳", "groups": [["먼곳"], ["먼곳(가)"]]}] or apart[0]["name"] == "먼곳"
    assert sum(1 for s in st if s["name"] == "먼곳") == 2


def test_station_layer_ids_are_url_safe_and_samseong_merged():
    feats = layer("stations.geojson")
    ids = [f["id"] for f in feats]
    assert len(ids) == len(set(ids)) and all(__import__("re").fullmatch(r"station:[A-Za-z0-9]+", i) for i in ids)
    sam = [f["properties"] for f in feats if f["properties"]["name"] == "삼성"]
    assert len(sam) == 1 and sam[0]["aliases"] == ["삼성", "삼성(무역센터)"]


# ---------- 버스정류장·노선 ----------
STOPS = [
    {"정류장_ID": "122000001", "정류장_명칭": "강남역", "정류장_유형": "중앙차로", "정류장_번호": "22001", "위도": "37.498", "경도": "127.0276"},
    {"정류장_ID": "122000002", "정류장_명칭": "강남역", "정류장_유형": "일반차로", "정류장_번호": "22002", "위도": "37.4981", "경도": "127.0277"},
    {"정류장_ID": "122000003", "정류장_명칭": "한남대교(가상)", "정류장_유형": "가상정류장", "정류장_번호": "0", "위도": "37.52", "경도": "127.01"},
    {"정류장_ID": "122000004", "정류장_명칭": "선착장", "정류장_유형": "선착장", "정류장_번호": "00004", "위도": "37.53", "경도": "127.02"},
    {"정류장_ID": "122000005", "정류장_명칭": "노선없음", "정류장_유형": "일반차로", "정류장_번호": "02005", "위도": "37.49", "경도": "127.03"},
    {"정류장_ID": "122000006", "정류장_명칭": "좌표없음", "정류장_유형": "일반차로", "정류장_번호": "22006", "위도": "0", "경도": "0"},
]
ROUTES = [{"노선_ID": "100100025", "노선_명칭": "146", "노선_유형": "간선", "거리": ""},
          {"노선_ID": "123000013", "노선_명칭": "N73", "노선_유형": "", "거리": ""}]
ROUTE_STOPS = [
    {"노선_ID": "100100025", "정류장_ID": "122000002", "링크_구간거리(m)": "1", "정류장_순서": "12"},
    {"노선_ID": "100100025", "정류장_ID": "122000001", "링크_구간거리(m)": "1", "정류장_순서": "3"},
    {"노선_ID": "100100025", "정류장_ID": "122000001", "링크_구간거리(m)": "1", "정류장_순서": "40"},   # 순환: 같은 정류장 두 번
    {"노선_ID": "100100025", "정류장_ID": "232000857", "링크_구간거리(m)": "1", "정류장_순서": "5"},    # 경기 정류장 (마스터에 없음)
    {"노선_ID": "123000013", "정류장_ID": "122000002", "링크_구간거리(m)": "1", "정류장_순서": "1"},
]


def test_bus_build_links_types_order_and_exclusions():
    feats, routes, rep = fp.bus_build(STOPS, ROUTES, ROUTE_STOPS, IN, NO_ZONES)
    by = {f["properties"]["ars_no"]: f["properties"] for f in feats}
    assert set(by) == {"22001", "22002", "02005"}                         # ARS 앞자리 0 보존, 가상·선착장·좌표 0 제외
    assert rep["excluded"] == {"정류장 유형 '가상정류장'": 1, "정류장 유형 '선착장'": 1}
    assert rep["excluded_outside"] == {"좌표 없음 또는 0": 1}
    assert by["22001"]["route_ids"] == ["100100025"] and by["22001"]["central_lane"] is True
    assert by["22002"]["route_ids"] == ["100100025", "123000013"]
    assert by["22002"]["route_types"] == {"": 1, "간선": 1}                # 빈 유형은 빈 값 그대로
    assert by["02005"]["route_count"] == 0                                # 노선 없는 정류장도 레이어에 남김
    # 같은 이름이어도 합치지 않음 (길 양쪽 정류장), 100m 안이면 서로 '같은 이름 정류장'
    assert by["22001"]["same_name_nearby"] == ["bus:22002"] and by["22002"]["same_name_nearby"] == ["bus:22001"]
    r146 = next(r for r in routes if r["route_no"] == "146")
    assert r146["gangnam_stop_ids"] == ["22001", "22002", "22001"]       # 순번 순, 반복 그대로
    assert set(r146) == {"route_id", "route_no", "route_type", "gangnam_stop_ids", "as_of"}   # 기점·종점 필드 없음
    assert rep["route_stop_rows_dropped"]["정류장_ID가 서울 정류장 마스터에 없음 (경기·인천 등)"] == 1
    assert rep["link_rate_all"] == {"num": 4, "den": 5}
    assert rep["link_rate_gangnam"] == {"num": 2, "den": 3}


def test_bus_duplicate_ars_rule_keeps_smaller_stop_id():
    dup = [dict(STOPS[1]), dict(STOPS[1], 정류장_ID="122000000", 정류장_명칭="같은번호")]
    feats, _, rep = fp.bus_build(dup, ROUTES, [], IN, NO_ZONES)
    assert [f["properties"]["stop_id"] for f in feats] == ["122000000"]
    assert rep["duplicate_ars"] == {"22002": ["122000000", "122000002"]}


def test_norm_id_keeps_string_form():
    assert fp.norm_id(" 012345678 ") == "012345678"


def test_bus_layer_no_virtual_or_pier_and_names_not_merged():
    feats = layer("bus_stops.geojson")
    types = {f["properties"]["stop_type"] for f in feats}
    assert "가상정류장" not in types and "선착장" not in types
    ars = [f["properties"]["ars_no"] for f in feats]
    assert len(ars) == len(set(ars)) and all(len(a) == 5 and a.isdigit() for a in ars)
    names = [f["properties"]["name"] for f in feats]
    assert len(set(names)) < len(names)                                    # 같은 이름 정류장이 따로 남아 있음
    no_route = {f["properties"]["ars_no"] for f in feats if not f["properties"]["route_count"]}
    assert no_route == {"23811", "23910"}                                  # 역삼역·강남관광정보센터 (D3)


def test_bus_routes_json_sorted_by_sequence():
    d = json.loads((LAYERS / "bus_routes.json").read_text(encoding="utf-8"))
    by = {r["route_no"]: r for r in d["routes"]}
    assert {"146", "3412", "강남01"} <= set(by)
    assert by["146"]["route_type"] == "간선" and by["강남01"]["route_type"] == "마을"
    stops = {f["properties"]["ars_no"] for f in layer("bus_stops.geojson")}
    for r in d["routes"]:
        assert set(r["gangnam_stop_ids"]) <= stops and "start_stop" not in r and "end_stop" not in r


# D2 좌표 검증: 강남역·선릉역·삼성역 관련 정류장 6곳이 해당 역 좌표에서 300m 안 (원자료 위도·경도 그대로)
FIXED = {"22339": "강남", "22348": "강남", "23276": "선릉", "23218": "선릉", "23244": "삼성", "23438": "삼성"}


def test_bus_stop_coordinates_within_300m_of_station():
    st = {f["properties"]["name"]: f["properties"] for f in layer("stations.geojson")}
    bus = {f["properties"]["ars_no"]: f["properties"] for f in layer("bus_stops.geojson")}
    for ars, name in FIXED.items():
        b, s = bus[ars], st[name]
        d = fp.haversine_m(b["lon"], b["lat"], s["lon"], s["lat"])
        assert d <= 300, (ars, b["name"], name, round(d))
        assert 126 < b["lon"] < 128 and 37 < b["lat"] < 38                 # WGS84 그대로 (TM 아님)


# ---------- 공통 ----------
def test_within_impact_on_layers():
    for name in ("schools.geojson", "stations.geojson", "bus_stops.geojson"):
        for f in layer(name):
            p = f["properties"]
            assert p["impact_buffer_m"] == p["within_impact"]["buffer_m"]
            assert p["within_impact"]["buffer_m"] in (None, 250, 500)
    # 영향권 밖 역은 null
    st = {f["properties"]["name"]: f["properties"] for f in layer("stations.geojson")}
    assert st["역삼"]["impact_buffer_m"] is None


def test_manifest_license_and_as_of_note():
    m = json.loads((LAYERS / "manifest.json").read_text(encoding="utf-8"))["layers"]
    for k in ("schools", "stations", "bus_stops", "bus_routes", "pois"):
        e = m[k]
        assert e["license"] and e["source"] and e["as_of"] and e["dataset_id"] and e["url"].startswith("https://")
    for k in ("stations", "bus_stops", "bus_routes"):
        assert "파일 내 기준일 없음, 내려받은 날 기준" in m[k]["as_of_note"] and m[k]["as_of"] == "2026-11-11"
        assert m[k]["license"].startswith("공공누리 1유형")
    assert m["schools"]["as_of"] == "2026-10-01" and m["pois"]["as_of"] == "202609"
    assert m["schools"]["license"].startswith("확인 필요")
    assert m["pois"]["license"] == "이용허락범위 제한 없음"
    assert sum(c["count"] for c in m["pois"]["categories"]) == m["pois"]["count"]
    sup = next(c for c in m["pois"]["categories"] if c["key"] == "supermarket")
    assert "대형마트" in sup["note"]


def test_saved_files_have_no_keys():
    from dotenv import dotenv_values
    vals = [v for v in dotenv_values(ROOT / ".env").values() if v and len(v) >= 16 and not v.startswith("http")] \
        if (ROOT / ".env").exists() else []
    files = list(LAYERS.glob("*.geojson")) + [LAYERS / "bus_routes.json", LAYERS / "manifest.json", FIX]
    for p in files:
        t = p.read_text(encoding="utf-8")
        assert "serviceKey=" not in t
        assert not any(v in t for v in vals), p.name


def test_m24_counts_match():
    from evals.run_eval import infra_metrics
    errs: list = []
    ms, info = infra_metrics(errs)
    assert ms[0]["id"] == "M24"
    if info is None:
        pytest.skip("레이어 없음")
    for r in info["sources"]:
        if r["raw"] is not None:
            assert r["ok"], r
    assert not errs


@pytest.mark.skipif(not fp.STOP_CSV.exists(), reason="원본 CSV(data_raw/12.생활인프라)가 없음 — 커밋하지 않는 파일")
def test_idempotent_rebuild(tmp_path, monkeypatch):
    """두 번 빌드해 같은 바이트 (캐시만 사용, 네트워크 없음)"""
    if not any(fp.RAW.glob("p*.json")):
        pytest.skip("상가 원 응답 캐시 없음")
    before = {p.name: p.read_bytes() for p in LAYERS.glob("*") if p.name.startswith(("schools", "stations", "bus_", "pois", "manifest"))}
    monkeypatch.setattr("sys.argv", ["fetch_pois", "--offline"])
    monkeypatch.setattr(fp, "REPORT", tmp_path / "report.json")
    fp.main()
    after = {p.name: p.read_bytes() for p in LAYERS.glob("*") if p.name.startswith(("schools", "stations", "bus_", "pois", "manifest"))}
    assert before == after
