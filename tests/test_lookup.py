from datetime import date
from pathlib import Path

from core.lookup import lookup

ROOT = Path(__file__).resolve().parents[1]
A1 = "강남구 압구정동 527"


def all_items(resp):
    L = resp["layers"]
    return L["city"] + L["gu"]["items"] + L["dong"]["items"] + L["parcel"]["items"] + resp["reference"]["items"]


def keys(items):
    return [i["item_key"] for i in items]


def test_a1_four_layers_have_entries(con):
    r = lookup(con, A1)
    assert r["status"] == "ok"
    L = r["layers"]
    assert len(L["city"]) >= 1
    assert len(L["gu"]["items"]) >= 1
    assert len(L["dong"]["items"]) >= 1
    # 필지 층에는 필지 범위 항목이 없고, 사업 포함 판정 카드가 이 층의 항목이다 (agents.md §4 A1)
    assert len(L["parcel"]["items"]) + len(L["parcel"]["included_projects"]) >= 1


def test_a1_dong_layer_has_d5_and_d1_no_saenghwal(con):
    dong = keys(lookup(con, A1)["layers"]["dong"]["items"])
    assert {"D5-01", "D1-01", "D1-02"} <= set(dong)
    assert not any(k.startswith("D2-") for k in dong)      # 지역생활권은 층에 두지 않는다 (feedback.md §4)


def test_a1_layer_caps_and_background_out(con):
    r = lookup(con, A1)
    L = r["layers"]
    assert len(L["city"]) <= 5 and len(L["gu"]["items"]) <= 2 and len(L["dong"]["items"]) <= 5
    placed = set(keys(L["city"] + L["gu"]["items"] + L["dong"]["items"] + L["parcel"]["items"]))
    assert not placed & {"D3-01", "D3-02", "D3-03", "D3-04", "D1-03"}   # 연혁·통계·생략 항목은 배경
    assert "D6-01" in keys(L["city"])
    assert all(i["tier"] == "applies" for i in L["city"] + L["gu"]["items"] + L["dong"]["items"])


def test_regulations_by_dong(con):
    for text in (A1, "강남구 압구정동 426"):            # A1, A5
        assert "D5-01" in keys(lookup(con, text)["layers"]["dong"]["items"]), text
    for text in ("강남구 청담동 134-38", "강남구 역삼동 737"):   # A6, A8
        assert "D5-01" not in keys(lookup(con, text)["layers"]["dong"]["items"]), text
    for text in (A1, "강남구 역삼동 737"):
        assert "D6-01" in keys(lookup(con, text)["layers"]["city"]), text


def test_reference_section(con):
    ref = lookup(con, A1)["reference"]
    assert ref["note"] and len(ref["items"]) <= 5
    assert sum(i["scope_type"] == "SAENGHWAL" for i in ref["items"]) <= 2
    assert {"D2-11", "D2-13"} <= set(keys(ref["items"]))
    assert all(i["reference_reason"] and i["layer"] for i in ref["items"])
    over = [i for i in ref["items"] if i["reference_reason"] == "층별 5개 초과"]
    assert over and all(i["layer"] == "city" for i in over)
    assert "D2-11" not in keys(lookup(con, "강남구 역삼동 737")["reference"]["items"])   # 다른 생활권


def test_effective_period_fields(con):
    d5 = next(i for i in lookup(con, A1, today=date(2026, 10, 26))["layers"]["dong"]["items"] if i["item_key"] == "D5-01")
    assert (d5["effective_from"], d5["effective_to"]) == ("2026-04-27", "2027-04-26")
    assert d5["effective_label"] == "효력 기간 2026.04.27 ~ 2027.04.26"
    assert (d5["effective_status"], d5["effective_status_label"]) == ("in_force", "효력 기간 중")
    assert d5["target_note"].startswith("대상: 압구정 아파트지구")
    assert d5["more_evidence"] and all(m["evidence_ok"] for m in d5["more_evidence"])
    d7 = next(i for i in lookup(con, A1)["layers"]["city"] if i["item_key"] == "D7-01")
    assert d7["effective_label"] == "효력 2025.10.16부터" and d7["effective_to"] is None


def test_ended_regulation_moves_to_reference(con):
    r = lookup(con, A1, today=date(2027, 5, 1))     # D6(~2026.12.31)·D5(~2027.4.26) 효력 끝남
    assert "D6-01" not in keys(r["layers"]["city"]) and "D5-01" not in keys(r["layers"]["dong"]["items"])
    ended = {i["item_key"]: i for i in r["reference"]["items"] if i["reference_reason"] == "효력 기간 끝남"}
    assert {"D5-01", "D6-01"} <= set(ended)
    assert ended["D6-01"]["effective_status_label"] == "효력 기간 끝남"


def test_not_started_stays_in_layer(con):
    r = lookup(con, A1, today=date(2026, 4, 20))
    d5 = next(i for i in r["layers"]["dong"]["items"] if i["item_key"] == "D5-01")
    assert d5["effective_status"] == "not_started" and d5["effective_status_label"] == "효력 시작 전"


def test_a1_hanyang7_possible(con):
    inc = lookup(con, A1)["layers"]["parcel"]["included_projects"]
    assert len(inc) == 1
    p = inc[0]
    assert p["inclusion"] == "possible" and p["inclusion_label"] == "포함될 수 있음"
    assert p["basis"] == "representative_only"
    assert p["message"].endswith("구역에 포함될 수 있습니다")
    assert p["review_id"] is not None and p["source"]["page_image"]


def test_project_not_duplicated_in_dong_layer(con):
    r = lookup(con, A1)
    ids = {p["project_id"] for p in r["layers"]["parcel"]["included_projects"]}
    assert ids and not ids & {p["project_id"] for p in r["layers"]["dong"]["projects"]}


def test_same_dong_other_parcel_shows_dong_project(con):
    r = lookup(con, "강남구 압구정동 429")
    assert r["layers"]["parcel"]["included_projects"] == []
    dp = r["layers"]["dong"]["projects"]
    assert [p["name"] for p in dp] == ["압구정아파트지구 특별계획구역6-1 재건축 정비구역"]


def test_a2_road_address_input(con):
    r = lookup(con, "서울특별시 강남구 압구정로61길 37")
    assert r["status"] == "ok" and r["normalized"]["addr_id"] == "A2"
    assert r["normalized"]["pnu"] == "1168011000105280000"   # 527은 도로명이 없어 인접 528
    assert r["layers"]["parcel"]["included_projects"] == []
    assert [p["project_id"] for p in r["layers"]["dong"]["projects"]] == [1]


def test_a4_nearby_with_distance(con):
    r = lookup(con, "강남구 압구정동 494")
    near = r["layers"]["parcel"]["nearby_projects"]
    assert len(near) == 1 and 0 < near[0]["distance_m"] <= 500
    assert near[0]["inclusion"] == "nearby" and "사업 중심" in near[0]["distance_basis"]
    assert r["layers"]["dong"]["projects"] == []   # 필지 층에 나온 사업은 법정동 층에서 뺀다


def test_a5_same_dong_outside_500m(con):
    r = lookup(con, "강남구 압구정동 426")
    assert r["layers"]["parcel"]["nearby_projects"] == []
    assert r["layers"]["parcel"]["nearby_note"] is None
    assert [p["project_id"] for p in r["layers"]["dong"]["projects"]] == [1]


def test_a10_road_address_out_of_scope(con):
    assert lookup(con, "서울특별시 서초구 방배중앙로13길 26")["status"] == "out_of_scope"


def test_a8_other_dong(con):
    r = lookup(con, "강남구 역삼동 737")
    L = r["layers"]
    assert L["parcel"]["included_projects"] == [] and L["dong"]["projects"] == []
    assert L["dong"]["items"] == []                       # 압구정 항목 없음
    assert "지역생활권 장은 프리토타입 범위 밖" not in r["coverage_note"]
    assert "2030 생활권계획(2018)은 참고로만 보여줍니다" in r["coverage_note"]
    assert len(L["city"]) >= 1 and len(L["gu"]["items"]) >= 1


def test_a10_out_of_scope(con):
    r = lookup(con, "서초구 방배동 818-14")
    assert r["status"] == "out_of_scope" and r["layers"] is None
    assert r["message"] == "시연 범위(강남구) 밖입니다"


def test_items_have_source_and_page_image_file(con):
    for text in (A1, "강남구 역삼동 737"):
        for it in all_items(lookup(con, text)):
            s = it["source"]
            assert s["pdf_page"] and s["page_image"], it["item_key"]
            assert (ROOT / "public" / s["page_image"].lstrip("/")).exists(), s["page_image"]
            assert it["evidence"] and it["summary"]


def test_layer_placement_rules(con):
    L = lookup(con, A1)["layers"]
    assert all(i["scope_type"] == "SIDO" for i in L["city"])
    assert all(i["scope_type"] == "SGG" for i in L["gu"]["items"])
    assert all(i["scope_type"] == "BJD" for i in L["dong"]["items"])


def test_land_use_and_nearby_note(con):
    P = lookup(con, A1)["layers"]["parcel"]
    assert P["land_use"]["value"] == "제3종일반주거지역"
    assert P["land_use"]["basis"].startswith("사업 문서 기재")   # 사업 문서 기재값이 건축물대장보다 앞선다
    assert P["nearby_projects"] == []
    assert P["nearby_note"]   # 좌표가 없으면 생략 사유를 알린다


def test_building_or_note(con):
    for text in (A1, "강남구 역삼동 737", "강남구 논현동 100"):
        P = lookup(con, text)["layers"]["parcel"]
        assert ("building" in P and "building_note" in P), text
        assert (P["building"] is None) == bool(P["building_note"]), text
    P = lookup(con, "강남구 논현동 100")["layers"]["parcel"]       # 시연 주소가 아닌 필지는 조회하지 않았다
    assert P["building"] is None and "조회하지 않았습니다" in P["building_note"]


def test_projects_by_stage(con):
    gu = lookup(con, A1)["layers"]["gu"]
    assert gu["projects_by_stage"] == {"RB02": {"title": "정비계획 입안·주민공람", "count": 1}}
