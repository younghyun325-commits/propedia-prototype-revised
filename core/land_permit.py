"""토지거래허가 대상 필지별 판정 (P22-1, 요청 16). 표준 라이브러리만, 네트워크 없음.

land_permit_status()는 순수 함수다. 필요한 사실(지역지구·이용상황·건축물대장·단지 지번)은 permit_facts()가 모은다.
근거 고시
- D5 서울특별시 공고 제2026-1141호: 압구정 아파트지구 재지정, 용도 제한 문구 없음 (D5 p1)
- D6 국토교통부공고 제2025-1219호: 서울 25개 구 아파트·연립·다세대, 연립·다세대는 붙임2 단지만 (D6 p1·p4)
- 서울특별시 공고 제2025-2774호: 강남구 14개 동 아파트 (data_raw/13.토지거래허가_서울시, 문서 DB 미반영)
결과 상태
- required       허가 대상 (아파트 또는 아파트 단지 안)
- required_zone  허가 대상 (구역 지정: 건물 종류와 관계없이)
- not_target     구역 안이지만 대상 아님 (건축물대장 기준)
- unknown        확인 필요
"""
from datetime import date

from core.timeutil import parse_date

APGUJEONG_BJD = "1168011000"
APT_ZONE = "아파트지구"
PERMIT_ZONE = "토지거래계약에관한허가구역"
D6_MIXED_COMPLEX_PNUS: frozenset[str] = frozenset()

SEOUL_2774 = {
    "label": "서울특별시 공고 제2025-2774호",
    "gosi_no": "서울특별시 공고 제2025-2774호",
    "published_at": "2025-09-25",
    "effective_from": "2025-10-01",
    "effective_to": "2026-12-31",
    "evidence": "※ 건축법 시행령 별표1(용도별 건축물의 종류) 제2호 가목인 경우로 한정",
    "source_note": "강남구청 고시공고 게시물 첨부 (data_raw/13.토지거래허가_서울시, 문서 DB 미반영)",
    "source_url": "https://www.gangnam.go.kr/board/B_000046/1075065/view.do?mid=ID05_0410",
}

STATUS_LABELS = {
    "required": "허가 대상",
    "required_zone": "허가 대상 (구역 지정)",
    "not_target": "구역 안이지만 대상 아님",
    "unknown": "확인 필요",
}
MESSAGES = {
    "required": "이 땅의 집을 사려면 구청 허가가 필요해요",
    "required_zone": "이 땅은 구역 전체가 허가 대상이라 건물 종류와 관계없이 사고팔 때 구청 허가가 필요해요",
    "not_target": "구역 안이지만 이 건물 종류는 허가 없이 거래할 수 있어요",
    "unknown": "건물 종류를 확인하지 못해 허가 대상인지 아직 알 수 없어요",
}
REASONS = {
    "apt_complex": "실거래 아파트 단지의 신고 지번이에요",
    "apt_building": "건축물대장 용도가 아파트예요",
    "mixed_complex": "공고 붙임2의 아파트·연립 혼재 단지예요",
    "apt_zone": "압구정 아파트지구 안이에요 (토지이용계획 지역지구 '아파트지구')",
    "multi": "건축물대장 용도가 연립·다세대주택이고 아파트 단지에 속하지 않아요",
    "detached": "건축물대장 용도가 단독주택이에요",
    "other": "건축물대장 용도가 주택이 아니에요",
    "no_building": "건축물대장 정보가 없어요",
    "group_only": "건축물대장 요약에 아파트·연립·다세대 구분이 없어요",
    "no_land": "토지이용계획을 불러오지 못해 압구정 아파트지구 안인지 알 수 없어요",
    "expired": "판정에 쓰는 고시의 지정 기간이 끝났고 연장 공고를 확인하지 못했어요",
    "before": "이 기준일에는 판정에 쓰는 고시가 아직 효력 전이에요",
}
EXTENSION_UNKNOWN = "연장 여부 확인 필요"


def _purposes(building: dict | None) -> list[str]:
    if not building:
        return []
    out = [str(p) for p in (building.get("detail_purposes") or []) if p]
    if building.get("main_purpose"):
        out.append(str(building["main_purpose"]))
    return out


def building_kind(building: dict | None) -> str | None:
    """건축물대장 요약 → apartment | multi | detached | other | group(공동주택만) | None(정보 없음)"""
    ps = _purposes(building)
    if not ps:
        return None
    if any("아파트" in p for p in ps):
        return "apartment"
    if any("연립" in p or "다세대" in p for p in ps):
        return "multi"
    if any(k in p for p in ps for k in ("단독", "다가구", "다중주택")):
        return "detached"
    if all(p == "공동주택" for p in ps):
        return "group"
    return "other"


def _dot(iso: str | None) -> str:
    return iso.replace("-", ".") if iso else ""


def deadline_label(effective_to: str | None, today: date, extension_known: bool) -> str | None:
    if not effective_to:
        return None
    end = parse_date(effective_to)
    tail = "" if extension_known else f" ({EXTENSION_UNKNOWN})"
    if end < today:
        return f"{_dot(effective_to)}에 기간이 끝났어요{tail}"
    return f"{_dot(effective_to)}까지{tail}"


def _in_force(frm: str | None, to: str | None, today: date) -> bool:
    return (not frm or parse_date(frm) <= today) and (not to or today <= parse_date(to))


def land_permit_status(pnu: str, *, zones: list[str] | None, building: dict | None,
                       apartment_pnus: frozenset[str] | set[str], regs: dict, today: date,
                       mixed_complex_pnus: frozenset[str] = D6_MIXED_COMPLEX_PNUS) -> dict:
    """필지 하나 → 판정. regs = {"D5": 항목, "D6": 항목} (effective_to·source 등, permit_facts가 DB에서 채움)"""
    bjd = pnu[:10]
    zone_names = set(zones or [])
    kind = building_kind(building)
    d5, d6 = regs.get("D5"), regs.get("D6")

    def basis_d6() -> list[dict]:
        out = []
        if d6:
            out.append({"label": d6["gosi_no"], "effective_from": d6["effective_from"], "effective_to": d6["effective_to"],
                        "evidence": d6["target_note"], "source": d6["source"], "source_note": None, "source_url": None})
        out.append({"label": SEOUL_2774["label"], "effective_from": SEOUL_2774["effective_from"],
                    "effective_to": SEOUL_2774["effective_to"],
                    "evidence": SEOUL_2774["evidence"], "source": None, "source_note": SEOUL_2774["source_note"],
                    "source_url": SEOUL_2774["source_url"]})
        return out

    def result(status: str, reason: str, basis: list[dict], effective_to: str | None, extension_known: bool) -> dict:
        return {"pnu": pnu, "status": status, "status_label": STATUS_LABELS[status], "message": MESSAGES[status],
                "reason": REASONS[reason], "reason_code": reason, "basis": basis,
                "effective_to": effective_to,
                "deadline_label": deadline_label(effective_to, today, extension_known),
                "building_kind": kind}

    apt_from = min((b["effective_from"] for b in basis_d6() if b["effective_from"]), default=None)
    apt_to = max((b["effective_to"] for b in basis_d6() if b["effective_to"]), default=None)

    if bjd == APGUJEONG_BJD and APT_ZONE in zone_names and d5 and _in_force(d5["effective_from"], d5["effective_to"], today):
        basis = [{"label": d5["gosi_no"], "effective_from": d5["effective_from"], "effective_to": d5["effective_to"],
                  "evidence": d5["target_note"], "source": d5["source"], "source_note": None, "source_url": None}]
        return result("required_zone", "apt_zone", basis, d5["effective_to"], True)
    if apt_from and today < parse_date(apt_from):
        return result("unknown", "before", basis_d6(), apt_to, False)
    if apt_to and today > parse_date(apt_to):
        return result("unknown", "expired", basis_d6(), apt_to, False)
    if pnu in apartment_pnus:
        return result("required", "apt_complex", basis_d6(), apt_to, False)
    if kind == "apartment":
        return result("required", "apt_building", basis_d6(), apt_to, False)
    if pnu in mixed_complex_pnus:
        return result("required", "mixed_complex", basis_d6(), apt_to, False)
    if bjd == APGUJEONG_BJD and zones is None:
        return result("unknown", "no_land", basis_d6(), apt_to, False)
    if kind in ("multi", "detached", "other"):
        return result("not_target", kind, basis_d6(), apt_to, False)
    return result("unknown", "group_only" if kind == "group" else "no_building", basis_d6(), apt_to, False)


def _apartment_pnus(features: list[dict]) -> frozenset[str]:
    out: set[str] = set()
    for f in features:
        raw = (f.get("properties") or {}).get("pnus") or ""
        items = raw if isinstance(raw, list) else str(raw).split(",")
        out.update(p.strip() for p in items if p and p.strip())
    return frozenset(out)


def permit_facts(con, items: list[dict], apartment_features: list[dict]) -> tuple[dict, frozenset[str]]:
    """DB 항목(load_items 결과)에서 D5-01·D6-01, 아파트 레이어에서 단지 지번 PNU 집합"""
    regs = {}
    docs = {r["doc_id"]: r for r in con.execute("SELECT doc_id, gosi_no FROM documents WHERE doc_id IN ('D5','D6')")}
    for it in items:
        doc = (it.get("source") or {}).get("doc_id")
        if it["item_key"] in ("D5-01", "D6-01") and doc in docs:
            regs[doc] = {"gosi_no": docs[doc]["gosi_no"], "effective_from": it["effective_from"],
                         "effective_to": it["effective_to"],
                         "target_note": it["target_note"], "source": it["source"]}
    return regs, _apartment_pnus(apartment_features)
