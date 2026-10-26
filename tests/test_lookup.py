from pathlib import Path

from core.lookup import lookup

ROOT = Path(__file__).resolve().parents[1]
A1 = "강남구 압구정동 527"


def all_items(resp):
    L = resp["layers"]
    return L["city"] + L["gu"]["items"] + L["dong"]["items"] + L["parcel"]["items"]


def test_a1_four_layers_have_entries(con):
    r = lookup(con, A1)
    assert r["status"] == "ok"
    L = r["layers"]
    assert len(L["city"]) >= 1
    assert len(L["gu"]["items"]) >= 1
    assert len(L["dong"]["items"]) >= 1
    # 필지 층에는 필지 범위 항목이 없고, 사업 포함 판정 카드가 이 층의 항목이다 (agents.md §4 A1)
    assert len(L["parcel"]["items"]) + len(L["parcel"]["included_projects"]) >= 1


def test_a1_dong_layer_has_d1_and_saenghwal_items(con):
    keys = {i["item_key"] for i in lookup(con, A1)["layers"]["dong"]["items"]}
    assert any(k.startswith("D1-") for k in keys)
    assert any(k.startswith("D2-") for k in keys)


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


def test_a8_other_saenghwal(con):
    r = lookup(con, "강남구 역삼동 737")
    L = r["layers"]
    assert L["parcel"]["included_projects"] == [] and L["dong"]["projects"] == []
    assert L["dong"]["items"] == []
    assert "역삼·논현 지역생활권 장은 프리토타입 범위 밖입니다" in r["coverage_note"]
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
    assert all(i["scope_type"] in ("BJD", "SAENGHWAL") for i in L["dong"]["items"])


def test_land_use_and_nearby_note(con):
    P = lookup(con, A1)["layers"]["parcel"]
    assert P["land_use"]["value"] == "제3종일반주거지역"
    assert P["nearby_projects"] == []
    assert P["nearby_note"]   # 좌표가 없으면 생략 사유를 알린다


def test_projects_by_stage(con):
    gu = lookup(con, A1)["layers"]["gu"]
    assert gu["projects_by_stage"] == {"RB02": {"title": "정비계획 입안·주민공람", "count": 1}}
