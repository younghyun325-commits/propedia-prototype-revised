"""P22-1 요청 16: 토지거래허가 대상 필지별 판정 (core/land_permit.py). 네트워크 없음."""
from datetime import date

import pytest

from core import map as map_mod
from core.land_permit import (EXTENSION_UNKNOWN, MESSAGES, REASONS, STATUS_LABELS, building_kind,
                              land_permit_status)

TODAY = date(2026, 11, 12)
SRC = {"doc_id": "D6", "pdf_page": 1}
REGS = {
    "D5": {"gosi_no": "서울특별시 공고 제2026-1141호", "effective_from": "2026-04-27", "effective_to": "2027-04-26",
           "target_note": "대상: 압구정 아파트지구", "source": {"doc_id": "D5", "pdf_page": 1}},
    "D6": {"gosi_no": "국토교통부공고 제2025-1219호", "effective_from": "2025-10-20", "effective_to": "2026-12-31",
           "target_note": "대상: 아파트, 연립주택, 다세대주택", "source": SRC},
}
APGUJEONG_527 = "1168011000105270000"
EUNMA = "1168010600103160000"
ILWON_DETACHED = "1168011400106310006"
YEOKSAM_823 = "1168010100108230000"
ZONES_GANGNAM = ["도시지역", "토지거래계약에관한허가구역"]
ZONES_APGUJEONG = ZONES_GANGNAM + ["아파트지구"]


def judge(pnu, *, zones=ZONES_GANGNAM, building=None, apts=frozenset(), today=TODAY, mixed=frozenset()):
    return land_permit_status(pnu, zones=zones, building=building, apartment_pnus=apts, regs=REGS, today=today,
                              mixed_complex_pnus=mixed)


def test_required_apartment_complex():
    r = judge(EUNMA, building={"main_purpose": "공동주택"}, apts=frozenset({EUNMA}))
    assert r["status"] == "required" and r["reason_code"] == "apt_complex"
    assert r["message"] == "이 땅의 집을 사려면 구청 허가가 필요해요"
    assert r["deadline_label"] == f"2026.12.31까지 ({EXTENSION_UNKNOWN})"
    assert [b["label"] for b in r["basis"]] == ["국토교통부공고 제2025-1219호", "서울특별시 공고 제2025-2774호"]


def test_required_apartment_by_building_register():
    r = judge("1168010600199990000", building={"main_purpose": "공동주택", "detail_purposes": ["아파트"]})
    assert r["status"] == "required" and r["reason_code"] == "apt_building"


def test_multi_in_apartment_complex_is_required():
    pnu = "1168010600199990001"
    r = judge(pnu, building={"main_purpose": "공동주택", "detail_purposes": ["연립주택"]}, apts=frozenset({pnu}))
    assert r["status"] == "required"
    r2 = judge(pnu, building={"main_purpose": "공동주택", "detail_purposes": ["다세대주택"]}, mixed=frozenset({pnu}))
    assert r2["status"] == "required" and r2["reason_code"] == "mixed_complex"


def test_required_zone_apgujeong():
    r = judge(APGUJEONG_527, zones=ZONES_APGUJEONG, building=None)
    assert r["status"] == "required_zone" and r["reason_code"] == "apt_zone"
    assert r["deadline_label"] == "2027.04.26까지"
    assert r["basis"][0]["label"] == "서울특별시 공고 제2026-1141호"


def test_d5_zone_wins_over_apartment_complex():
    r = judge(APGUJEONG_527, zones=ZONES_APGUJEONG, building={"main_purpose": "공동주택"},
              apts=frozenset({APGUJEONG_527}))
    assert r["status"] == "required_zone"


def test_d5_outside_period_falls_back_to_apartment_rule():
    r = judge(APGUJEONG_527, zones=ZONES_APGUJEONG, apts=frozenset({APGUJEONG_527}), today=date(2026, 3, 1))
    assert r["status"] == "required" and r["reason_code"] == "apt_complex"


def test_apgujeong_outside_apartment_zone_is_not_zone_rule():
    r = judge("1168011000100010000", zones=ZONES_GANGNAM, building={"main_purpose": "단독주택"})
    assert r["status"] == "not_target"


@pytest.mark.parametrize("building,reason", [
    ({"main_purpose": "단독주택"}, "detached"),
    ({"main_purpose": "공동주택", "detail_purposes": ["다세대주택"]}, "multi"),
    ({"main_purpose": "제2종근린생활시설"}, "other"),
])
def test_not_target(building, reason):
    r = judge(ILWON_DETACHED, building=building)
    assert r["status"] == "not_target" and r["reason_code"] == reason
    assert r["message"] == "구역 안이지만 이 건물 종류는 허가 없이 거래할 수 있어요"


def test_unknown_when_building_register_missing():
    r = judge(YEOKSAM_823, building=None)
    assert r["status"] == "unknown" and r["reason_code"] == "no_building"


def test_unknown_when_only_group_purpose():
    r = judge(ILWON_DETACHED, building={"main_purpose": "공동주택"})
    assert r["status"] == "unknown" and r["reason_code"] == "group_only"


def test_unknown_when_land_missing_in_apgujeong():
    r = judge(APGUJEONG_527, zones=None, building={"main_purpose": "단독주택"})
    assert r["status"] == "unknown" and r["reason_code"] == "no_land"


def test_expired_and_before():
    assert judge(EUNMA, apts=frozenset({EUNMA}), today=date(2027, 1, 1))["reason_code"] == "expired"
    assert "끝났어요" in judge(EUNMA, apts=frozenset({EUNMA}), today=date(2027, 1, 1))["deadline_label"]
    assert judge(EUNMA, apts=frozenset({EUNMA}), today=date(2025, 6, 1))["reason_code"] == "before"


def test_building_kind():
    assert building_kind(None) is None
    assert building_kind({"main_purpose": "공동주택"}) == "group"
    assert building_kind({"main_purpose": "공동주택", "detail_purposes": ["아파트", "연립주택"]}) == "apartment"
    assert building_kind({"main_purpose": "단독주택"}) == "detached"
    assert building_kind({"main_purpose": "업무시설"}) == "other"


def test_copy_matches_screen_text():
    ui = (map_mod.ROOT / "web" / "src" / "copy" / "ui.ts").read_text(encoding="utf-8")
    for text in [*STATUS_LABELS.values(), *MESSAGES.values(), *REASONS.values()]:
        assert text in ui, text


@pytest.mark.parametrize("pnu,status", [
    (APGUJEONG_527, "required_zone"),
    (EUNMA, "required"),
    (ILWON_DETACHED, "not_target"),
    (YEOKSAM_823, "unknown"),
])
def test_parcel_feature_has_permit(con, pnu, status):
    f = map_mod.map_feature(con, "parcel", f"parcel:{pnu}", None, TODAY)
    lp = f["sections"]["parcel"]["land_permit"]
    assert lp["status"] == status and lp["message"] == MESSAGES[status]
    assert lp["basis"] and all(b["label"] for b in lp["basis"])
