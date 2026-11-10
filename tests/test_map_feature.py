"""인스펙터 API (docs/map/PLAN.md P16): GET /api/v1/map/feature/{kind}/{id}. 네트워크 없음.

- A1(압구정동 527)·B1(일원동 619): 단계·기한·수치·근거 쪽이 기존 lookup()·progress() 응답과 같음
- 세 종류 응답 형식, 없는 id 404, as_of 날짜별 기한·효력 상태
- A2(528) 필지 보기: likely·검수 17 (실시간 조회 없이 빌드 캐시 경로)
- WMS 0단계 검사는 tests/test_map_wms.py
"""
import time
from datetime import date

import pytest

from core import map as map_mod
from core.lookup import lookup
from core.progress import progress

TODAY = date(2026, 11, 10)
PNU_528 = "1168011000105280000"
COMMON = {"kind", "id", "title", "kind_label", "badges", "as_of", "sections", "evidence"}
EVIDENCE_KEYS = {"doc_id", "short_title", "title", "gosi_no", "published_at", "pdf_page", "page_label", "evidence",
                 "page_image", "docs_url", "label"}


def feat(con, kind, fid, today=TODAY):
    return map_mod.map_feature(con, kind, fid, None, today)


def pages(src_list):
    return [(s["doc_id"], s["pdf_page"]) if s else None for s in src_list]


@pytest.mark.parametrize("query", ["강남구 압구정동 527", "강남구 일원동 619"])
def test_same_facts_as_lookup(con, query):
    lk = lookup(con, query, today=TODAY)
    inc = lk["layers"]["parcel"]["included_projects"]
    assert len(inc) == 1
    pid = inc[0]["project_id"]
    pr = progress(con, pid, today=TODAY)
    f = feat(con, "project", str(pid))
    fp = f["sections"]["progress"]
    assert [s["code"] for s in fp["stages"]] == [s["code"] for s in pr["stages"]]
    assert [s["status"] for s in fp["stages"]] == [s["status"] for s in pr["stages"]]
    assert fp["position_label"] == pr["position_label"] and fp["current"]["code"] == pr["current"]["code"]
    assert [(d["due_on"], d["d_day_label"], d["status"]) for d in fp["deadlines"]] == \
        [(d["due_on"], d["d_day_label"], d["status"]) for d in pr["deadlines"]]
    assert [(x["label"], x["value"], x["unit"]) for x in fp["facts"]] == [(x["label"], x["value"], x["unit"]) for x in pr["facts"]]
    assert pages(x["source"] for x in fp["facts"]) == pages(x["source"] for x in pr["facts"])
    assert fp["stage_basis"] == pr["stage_basis"]
    assert fp["remaining"]["note"] == "비교할 사례가 부족합니다"
    # 이 주소 필지의 판정·근거 쪽이 사업 필지 목록과 같음
    row = next(p for p in f["sections"]["parcels"] if p["pnu"] == lk["normalized"]["pnu"])
    assert (row["inclusion"], row["review_id"], row["basis_label"]) == \
        (inc[0]["inclusion"], inc[0]["review_id"], inc[0]["basis_label"])
    assert pages([row["source"]]) == pages([inc[0]["source"]])


def test_project_stepper(con):
    h = feat(con, "project", "1")["sections"]["stepper"]
    assert (h["total"], h["current_seq"], h["remaining_stages"]) == (13, 2, 11)
    assert h["position_label"] == "재건축 13단계 중 2번째" and h["next_title"] == "정비구역 지정 고시"
    d = feat(con, "project", "2")["sections"]["stepper"]
    assert (d["total"], d["current_seq"], d["remaining_stages"]) == (8, 1, 7)
    assert d["position_label"].startswith("모아타운 8단계 중 1번째")
    # 단계 툴팁: 템플릿 문구 그대로 (없으면 '사람이 작성' 안내), 법령 대조 전 초안
    st = feat(con, "project", "1")["sections"]["progress"]["stages"][0]
    assert st["what_happens_note"] and st["template_status"] == "법령 대조 전 초안"


@pytest.mark.parametrize("kind,fid", [("project", "1"), ("project", "2"), ("regulation", "D10"), ("regulation", "D5"),
                                      ("regulation", "D6"), ("regulation", "D10-01"), ("parcel", PNU_528),
                                      ("parcel", f"1:{PNU_528}")])
def test_common_shape(con, client, kind, fid):
    r = client.get(f"/api/v1/map/feature/{kind}/{fid}", params={"as_of": "2026-11-10"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert COMMON <= set(d) and d["kind"] == kind and d["id"] == fid and d["as_of"] == "2026-11-10"
    assert d["evidence"] and all(EVIDENCE_KEYS <= set(e) for e in d["evidence"])
    for e in d["evidence"]:
        assert e["docs_url"].startswith(f"/docs.html?doc={e['doc_id']}")
        assert e["page_image"] is None or e["page_image"] == f"/pages/{e['doc_id']}/p{e['pdf_page']:03d}.jpg"
    assert all({"text", "tone"} <= set(b) for b in d["badges"])


@pytest.mark.parametrize("path", ["project/99", "project/abc", "regulation/D99", "regulation/D1", "regulation/D3",
                                  "parcel/123", "parcel/9999999999999999999", "unknown/1"])
def test_not_found_404(client, path):
    r = client.get(f"/api/v1/map/feature/{path}")
    assert r.status_code == 404
    assert any("가" <= ch <= "힣" for ch in r.json()["detail"])


def test_bad_as_of_400(client):
    assert client.get("/api/v1/map/feature/project/1", params={"as_of": "2026/11/10"}).status_code == 400


def test_as_of_dates(con):
    may, nov = date(2026, 5, 1), date(2026, 11, 10)
    # P19: 한양7차는 첫 근거 문서(D1) 발행일 전이라 그날에는 이름·안내만
    h = feat(con, "project", "1", may)
    assert h["shown"] is False and h["sections"] == {} and "발행" in h["note"]
    d = feat(con, "project", "2", may)["sections"]["progress"]["deadlines"][0]
    assert (d["status"], d["d_day_label"]) == ("open", "D-day")
    assert feat(con, "project", "2", may)["sections"]["status_badges"] == ["공람 중", "승인 고시 미확인"]
    h = feat(con, "project", "1", nov)["sections"]["progress"]["deadlines"][0]
    assert (h["status"], h["d_day_label"]) == ("closed", "마감(2026.11.06)")
    d = feat(con, "project", "2", nov)["sections"]["progress"]["deadlines"][0]
    assert (d["status"], d["d_day_label"]) == ("closed", "마감(2026.05.01)")
    assert feat(con, "project", "1", nov)["sections"]["status_badges"] == ["공람 마감"]
    assert feat(con, "project", "2", nov)["sections"]["status_badges"] == ["공람 마감", "승인 고시 미확인"]
    # 규제 효력 상태 (원문 기간과 기준일 비교 — timeutil.effective 그대로)
    assert feat(con, "regulation", "D10", may)["sections"]["regulation"]["effective_status"] == "in_force"
    assert feat(con, "regulation", "D5", date(2026, 4, 20))["sections"]["regulation"]["effective_status"] == "not_started"
    assert feat(con, "regulation", "D6", date(2027, 1, 1))["sections"]["regulation"]["effective_status"] == "ended"


def test_map_projects_status_badges(con):
    ps = {p["id"]: p for p in map_mod.map_projects(con, TODAY)["projects"]}
    assert ps[1]["status_badges"] == ["공람 마감"]
    assert ps[2]["status_badges"] == ["공람 마감", "승인 고시 미확인"]
    assert ps[1]["status_badge"] and ps[2]["status_badge"]      # 기존 키 유지


def test_project_parcels_and_history(con):
    f = feat(con, "project", "1")
    rows = {p["pnu"]: p for p in f["sections"]["parcels"]}
    assert rows["1168011000105270000"]["inclusion"] == "possible" and rows["1168011000105270000"]["review_id"] == 1
    assert rows[PNU_528]["inclusion"] == "likely" and rows[PNU_528]["review_id"] == 17
    assert rows[PNU_528]["verified"] is False and rows[PNU_528]["name"] == "압구정동 528" and rows[PNU_528]["bbox"]
    dates = [h["date"] for h in f["sections"]["history"] if h["date"]]
    assert dates == sorted(dates, reverse=True) and len(f["sections"]["history"]) >= 7
    b = f["sections"]["boundary"]
    assert b and b["source"]["doc_id"] == "D1" and b["source"]["pdf_page"] == 18 and not b["verified"]
    d9 = feat(con, "project", "2")
    assert any(e["doc_id"] == "D9" and e["pdf_page"] == 12 and e["page_image"] for e in d9["evidence"])


def test_regulation_boundary(con):
    d10 = feat(con, "regulation", "D10")["sections"]
    assert d10["boundary"] and d10["boundary_note"] is None
    assert d10["regulation"]["effective_label"] == "효력 기간 2026.04.01 ~ 2028.04.01"
    d5 = feat(con, "regulation", "D5")["sections"]
    assert d5["boundary"] is None and d5["boundary_note"] == map_mod.D5_NOTE
    assert feat(con, "regulation", "D6")["sections"]["boundary_note"] is None    # 서울 전역 (경계 없음이 당연)


def test_parcel_528_likely_review_17(con, client):
    for fid in (PNU_528, f"1:{PNU_528}"):
        d = client.get(f"/api/v1/map/feature/parcel/{fid}").json()
        b = d["sections"]["project_banner"]
        assert len(b) == 1 and b[0]["inclusion"] == "likely" and b[0]["review_id"] == 17 and not b[0]["verified"]
        assert b[0]["short_name"] == "한양7차아파트 재건축" and b[0]["inclusion_label"] == "포함된 것으로 보임"
        p = d["sections"]["parcel"]
        assert p["status"] == "ok" and p["land"]["status"] in ("ok", "partial")
        assert p["boundary_note"]                       # 실시간 조회 없이 (pytest PROPEDIA_LIVE=0)
        assert set(p["layer_items"]) == {"city", "gu", "dong", "parcel"}
        assert {k: len(v) for k, v in p["layer_items"].items()} == p["layer_counts"]
        assert d["unverified"] is True


def test_p95_project_regulation(client):
    for path in ("project/1", "project/2", "regulation/D10", "regulation/D5"):
        client.get(f"/api/v1/map/feature/{path}")       # 데우기
        ms = []
        for _ in range(20):
            t = time.perf_counter()
            assert client.get(f"/api/v1/map/feature/{path}").status_code == 200
            ms.append((time.perf_counter() - t) * 1000)
        ms.sort()
        assert ms[int(len(ms) * 0.95) - 1] <= 300, (path, ms[-3:])
