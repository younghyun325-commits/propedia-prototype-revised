"""P19 '그날 기준' 판정·타임라인·고시 피드 (docs/map/PLAN.md P19).

- state_at(as_of) 날짜별 기대값 (지시서 표 그대로)
- 같은 날짜에 /map/projects · /map/notices · /map/feature · /feed · /timeline 이 같은 상태를 돌려주는지 교차 검사
- 실거래 as_of 범위, 잘못된 as_of·from·to 400, 응답 문구에 '예정' 없음
"""
import json
from datetime import date
from pathlib import Path

import pytest

from core import map as map_mod
from core.map import state_at

ROOT = Path(__file__).resolve().parents[1]
MARKET_DB = ROOT / "db" / "market.db"
HANYANG, DAECHEONG = 1, 2
EUNMA = "apt:11680-218"


def proj(st, pid):
    p = st["projects"][pid]
    if not p["shown"]:
        return None
    dl = p["progress"]["deadlines"][0]
    return {"badges": p["status_badges"], "d_day": dl["d_day_label"], "status": dl["status"]}


def reg(st, doc):
    return next(r for r in st["regulations"].values() if r["doc_id"] == doc)


def chips(st):
    return {n["doc_id"] for n in st["notices"]}


# ---- 날짜별 기대값 ----

def test_2026_05_01(con):
    st = state_at(con, date(2026, 5, 1))
    assert proj(st, HANYANG) is None                      # D1(2026-10-06 발행) 전
    assert st["projects"][HANYANG]["shown_from"] == "2026-10-06"
    p = proj(st, DAECHEONG)
    assert p["badges"][0] == "공람 중" and p["d_day"] == "D-day" and p["status"] == "open"


def test_2026_05_02(con):
    p = proj(state_at(con, date(2026, 5, 2)), DAECHEONG)
    assert p["badges"][0] == "공람 마감" and p["d_day"] == "마감(2026.05.01)" and p["status"] == "closed"


def test_2026_10_08(con):
    p = proj(state_at(con, date(2026, 10, 8)), HANYANG)
    assert p is not None and p["badges"] == ["공람 중"] and p["status"] == "open"


def test_2026_11_10(con):
    st = state_at(con, date(2026, 11, 10))
    assert proj(st, HANYANG)["d_day"] == "마감(2026.11.06)"
    assert proj(st, DAECHEONG)["d_day"] == "마감(2026.05.01)"


def test_2027_01_01_d6_ended(con):
    before, after = state_at(con, date(2026, 12, 31)), state_at(con, date(2027, 1, 1))
    assert reg(before, "D6")["status"] == "in_force" and "D6" in chips(before)
    assert reg(after, "D6")["status"] == "ended" and reg(after, "D6")["status_label"] == "종료"
    assert "D6" not in chips(after)                       # 상단 칩에서 빠짐


def test_d10_not_started_then_in_force(con):
    a, b = reg(state_at(con, date(2026, 3, 31)), "D10"), reg(state_at(con, date(2026, 4, 1)), "D10")
    assert (a["status"], a["status_label"]) == ("not_started", "효력 전")
    assert (b["status"], b["status_label"]) == ("in_force", "효력 중")


def test_documents_shown_by_publish_date(con):
    st = state_at(con, date(2026, 5, 1))
    shown = {k for k, d in st["documents"].items() if d["shown"]}
    assert "D1" not in shown and "D8" not in shown and {"D9", "D10", "D5"} <= shown


# ---- API 교차 검사 ----

DATES = ["2026-03-31", "2026-04-01", "2026-05-01", "2026-05-02", "2026-10-08", "2026-11-10", "2027-01-01"]


@pytest.mark.parametrize("d", DATES)
def test_cross_endpoints_same_state(con, client, d):
    st = state_at(con, date.fromisoformat(d))
    projects = client.get("/api/v1/map/projects", params={"as_of": d}).json()["projects"]
    notices = client.get("/api/v1/map/notices", params={"as_of": d}).json()
    feed = client.get("/api/v1/feed", params={"as_of": d, "limit": 200}).json()
    for p in projects:
        sp = st["projects"][p["id"]]
        assert p["shown"] == sp["shown"]
        f = client.get(f"/api/v1/map/feature/project/{p['id']}", params={"as_of": d}).json()
        assert f["shown"] == sp["shown"]
        if not sp["shown"]:
            continue
        assert p["status_badges"] == sp["status_badges"] == f["sections"]["status_badges"]
        assert p["deadline"]["d_day_label"] == f["sections"]["progress"]["deadlines"][0]["d_day_label"]
        # 피드의 그 사업 문서 기한 = 지도 사업 목록 기한
        fd = next(i for i in feed["items"] if i["sel"] == f"project:{p['id']}")
        assert fd["deadline"]["d_day_label"] == p["deadline"]["d_day_label"]
        # 인스펙터 근거 문서는 그날 발행된 것만
        assert all(h["date"] is None or h["date"] <= d for h in f["sections"]["history"] if h["kind"] == "document")
    # 상단 칩
    assert {n["doc_id"] for n in notices["items"]} == chips(st)
    # 규제 효력 상태: notices.regulations = 인스펙터 = 피드 관련 규제
    for r in notices["regulations"]:
        f = client.get(f"/api/v1/map/feature/regulation/{r['doc_id']}", params={"as_of": d}).json()
        assert f["status"] == r["status"] == f["sections"]["regulation"]["effective_status"]
        fi = next((i for i in feed["items"] if i["doc_id"] == r["doc_id"]), None)
        if fi:
            rel = next(x for x in fi["related"] if x["kind"] == "regulation")
            assert rel["status"] == r["status"]
    # 피드 = 발행일 ≤ 기준일 문서, 최신순
    docs = {k for k, x in st["documents"].items() if x["shown"]}
    assert {i["doc_id"] for i in feed["items"]} == docs and feed["total"] == len(docs)
    pub = [i["published_at"] for i in feed["items"]]
    assert pub == sorted(pub, reverse=True) and all(x <= d for x in pub)


def test_feed_recent_30d(client):
    items = client.get("/api/v1/feed", params={"as_of": "2026-05-01"}).json()["items"]
    recent = {i["doc_id"] for i in items if i["recent_30d"]}
    assert recent == {"D9", "D10", "D5"}                   # 04-17·04-10·04-09 (30일 안), D6·D7은 아님


def test_timeline_lanes(client, con):
    t = client.get("/api/v1/timeline").json()
    lanes = t["lanes"]
    assert len(lanes["publish"]) == con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    assert [(b["start"], b["end"], b["sel"]) for b in lanes["review"]] == [
        ("2026-04-17", "2026-05-01", "project:2"), ("2026-10-06", "2026-11-06", "project:1")]
    eff = {b["doc_id"]: (b["start"], b["end"]) for b in lanes["effective"]}
    assert eff["D5"] == ("2026-04-27", "2027-04-26") and eff["D6"] == ("2025-10-20", "2026-12-31")
    assert eff["D10"] == ("2026-04-01", "2028-04-01") and eff["D7"][1] is None
    assert {s["project_id"] for s in lanes["stage"]} == {1, 2}
    assert any(e["id"] == "db:as_of" for e in lanes["data_as_of"])
    for lane in lanes.values():                            # 날짜는 모두 YYYY-MM-DD
        for e in lane:
            for k in ("date", "start", "end"):
                if e.get(k):
                    date.fromisoformat(e[k])


def test_timeline_range_includes_overlapping_bars(client):
    t = client.get("/api/v1/timeline", params={"from": "2026-12-01", "to": "2026-12-31"}).json()["lanes"]
    assert not t["publish"] and not t["review"]
    assert {b["doc_id"] for b in t["effective"]} == {"D5", "D6", "D7", "D10"}   # 기간에 걸치는 막대는 포함


# ---- 잘못된 날짜, 금지어 ----

@pytest.mark.parametrize("path", ["/api/v1/map/projects", "/api/v1/map/notices", "/api/v1/feed",
                                  "/api/v1/map/feature/project/1", f"/api/v1/apartments/{EUNMA}/trades"])
@pytest.mark.parametrize("bad", ["2026/05/01", "2026-13-01", "today", "2026-5-1"])
def test_bad_as_of_400(client, path, bad):
    r = client.get(path, params={"as_of": bad})
    assert r.status_code == 400 and "YYYY-MM-DD" in r.json()["detail"]


@pytest.mark.parametrize("params", [{"from": "2026-13-01"}, {"to": "x"}, {"from": "2027-01-01", "to": "2026-01-01"}])
def test_bad_timeline_range_400(client, params):
    r = client.get("/api/v1/timeline", params=params)
    assert r.status_code == 400 and any("가" <= ch <= "힣" for ch in r.json()["detail"])


@pytest.mark.parametrize("d", DATES)
def test_no_forbidden_word(client, d):
    paths = ["/api/v1/map/projects", "/api/v1/map/notices", "/api/v1/feed", "/api/v1/timeline",
             "/api/v1/map/feature/project/1", "/api/v1/map/feature/project/2", "/api/v1/map/feature/regulation/D10"]
    for p in paths:
        body = json.dumps(client.get(p, params={"as_of": d}).json(), ensure_ascii=False)
        body = body.replace("정비예정구역", "")             # 법정 용어 (test_wording.ALLOW)
        assert "예정" not in body, p


def test_hidden_project_note_wording(con):
    f = map_mod.map_feature(con, "project", "1", today=date(2026, 5, 1))
    assert f["shown"] is False and f["sections"] == {} and "2026-10-06" in f["note"]


# ---- 실거래 as_of ----

@pytest.mark.skipif(not MARKET_DB.exists(), reason="db/market.db 없음")
def test_trades_as_of_range(client):
    full = client.get(f"/api/v1/apartments/{EUNMA}/trades").json()
    cut = client.get(f"/api/v1/apartments/{EUNMA}/trades", params={"as_of": "2020-01-15"}).json()
    assert cut["as_of"] == "2020-01-15"
    assert cut["points"] and all(p["contract_date"] <= "2020-01-15" for p in cut["points"])
    assert all(r["contract_date"] <= "2020-01-15" for r in cut["recent"])
    assert all(m["ym"] <= "2020-01" for m in cut["monthly"])
    assert len(cut["points"]) < len(full["points"])
    # 기준일이 든 달은 그날까지만 다시 센 건수 (해제 제외, 면적대 있음)
    part = next((m for m in cut["monthly"] if m["ym"] == "2020-01"), None)
    want = sum(1 for p in cut["points"] if p["contract_date"].startswith("2020-01") and not p["is_cancelled"])
    assert (part["count"] if part else 0) == want
    # 전 달까지는 빌드 집계와 같음
    fm = {m["ym"]: m["count"] for m in full["monthly"]}
    assert all(fm[m["ym"]] == m["count"] for m in cut["monthly"] if m["ym"] < "2020-01")
