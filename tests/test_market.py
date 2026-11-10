"""P17 실거래 단지·market.db·API (docs/map/PLAN.md P17). 네트워크 없음.

- 단지 묶기·면적대 경계값·단지명 정규화·월별 중위값·해제 제외·중복 제거: 가짜 거래로 임시 market.db를 만들어 확인
- API 형식·503·p95: 임시 DB(형식)와 실제 db/market.db(있을 때만, 속도)
- 개인 정보 성격 필드가 DB·GeoJSON·견본에 없는지, 키 문자열이 커밋 대상 산출물에 없는지
- 기본 정보 API 미등록이면 아무것도 바꾸지 않고 건너뛰는지
"""
import json
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote, quote_plus

import pytest
from fastapi.testclient import TestClient

import core.db as cdb
from core import market as mk
from pipeline import build_market_db as bm
from pipeline import build_trade_complexes as btc
from pipeline import fetch_apt_basis as fab
from pipeline.apt_names import norm_name
from pipeline.rtms_parse import DROP_FIELDS, number_same, record

ROOT = Path(__file__).resolve().parents[1]


def tr(**kw) -> dict:
    base = {"sggCd": "11680", "umdCd": "10600", "landCd": "1", "bonbun": "0316", "bubun": "0000", "aptSeq": "11680-218",
            "aptNm": "은마", "umdNm": "대치동", "jibun": "316", "excluUseAr": "76.79", "dealYear": "2026",
            "dealMonth": "10", "dealDay": "16", "dealAmount": "300,000", "floor": "7", "buildYear": "1979",
            "dealingGbn": "중개거래", "landLeaseholdGbn": "N"}
    return record(base | kw)


# ---------- 순수 함수 ----------

@pytest.mark.parametrize("m2,band", [(59.99, "~60"), (60.0, "60~85"), (84.99, "60~85"), (85.0, "85~102"),
                                     (101.99, "85~102"), (102.0, "102~135"), (134.99, "102~135"), (135.0, "135~"),
                                     (300.0, "135~"), (0.0, "~60"), (None, None)])
def test_area_band_edges(m2, band):
    assert mk.area_band(m2) == band


def test_default_band():
    assert mk.default_band({"~60": 3, "60~85": 9, "85~102": 9}) == "60~85"     # 같으면 작은 면적대
    assert mk.default_band({}) is None


@pytest.mark.parametrize("a,b", [("한양7차", "압구정한양 제7차 아파트"), ("래미안 (대치)", "래미안"), ("개포주공1단지", "개포주공 1단지"),
                                 ("ＳＫ뷰", "sk뷰"), ("현대 1차", "현대1차아파트")])
def test_norm_name_same(a, b):
    assert norm_name(a) == norm_name(b) or norm_name(a).endswith(norm_name(b)) or norm_name(b).endswith(norm_name(a))


def test_norm_name_rules():
    assert norm_name("압구정 한양 제7차 아파트") == "압구정한양7"
    assert norm_name("래미안(대치)") == "래미안"
    assert norm_name("개포주공1단지") == "개포주공1"
    assert norm_name("ＳＫ뷰") == "sk뷰"


def test_group_keys_multi_pnu_and_seq_less():
    rows = [tr(), tr(bonbun="0127", bubun="0005", jibun="127-5", dealDay="20"),     # 같은 aptSeq, 다른 필지
            tr(aptSeq=None, dealDay="21"),                                           # aptSeq 없음 → 같은 PNU 단지로
            tr(aptSeq=None, bonbun="0999", jibun="999", aptNm="나홀로"),               # aptSeq 없음, 새 PNU → pnu: 단지
            tr(aptNm="은마아파트", dealDay="30")]                                     # 최근 이름이 대표, 옛 이름은 aliases
    cx = btc.group(rows)
    assert set(cx) == {"11680-218", "pnu:1168010600109990000"}
    e = cx["11680-218"]
    assert e["pnus"] == ["1168010600101270005", "1168010600103160000"]
    assert e["name"] == "은마아파트" and e["aliases"] == ["은마"]
    assert e["trade_count"] == 4 and e["bjd_code"] == "1168010600"
    assert cx["pnu:1168010600109990000"]["apt_seq"] is None


# ---------- 임시 market.db ----------

@pytest.fixture()
def tmp_market(tmp_path, monkeypatch):
    rows = [tr(dealAmount="300,000"), tr(dealAmount="320,000", dealDay="20"), tr(dealAmount="340,000", dealDay="25"),
            tr(dealAmount="999,000", dealDay="26", cdealType="O", cdealDay="26.10.30"),        # 해제 → 집계 제외
            tr(dealAmount="150,000", excluUseAr="60.00", dealMonth="9"),                      # 60.00 → 60~85
            tr(dealAmount="100,000", excluUseAr="59.99", dealMonth="9"),                      # ~60
            tr(aptSeq="11680-999", aptNm="없는단지", bonbun="0001", jibun="1"),                 # 위치 없는 단지
            tr(aptSeq=None, bonbun="0777", jibun="777", aptNm="은마")]                          # 단지명으로 연결
    rows += [tr(dealAmount="310,000", dealDay="27"), tr(dealAmount="310,000", dealDay="27")]  # 같은 달 같은 레코드 2건
    number_same(rows)
    seed = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [127.06, 37.5]}, "properties": {
            "id": "apt:11680-218", "apt_seq": "11680-218", "name": "은마", "aliases": [], "pnus": ["1168010600103160000"],
            "bjd_code": "1168010600", "lat": 37.5, "lon": 127.06, "build_year": 1979}},
        {"type": "Feature", "geometry": None, "properties": {
            "id": "apt:11680-999", "apt_seq": "11680-999", "name": "없는단지", "aliases": [], "pnus": ["1168010600100010000"],
            "bjd_code": "1168010600", "lat": None, "lon": None, "build_year": 1979}}]}
    (tmp_path / "apartments.geojson").write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")
    db = tmp_path / "market.db"
    monkeypatch.setattr(bm, "load_trades", lambda: (rows, 1))
    monkeypatch.setattr(bm, "APT_SEED", tmp_path / "apartments.geojson")
    monkeypatch.setattr(bm, "DB", db)
    monkeypatch.setattr(bm, "BUILD", tmp_path)
    monkeypatch.setattr(bm, "UNLINKED", tmp_path / "unlinked.csv")
    monkeypatch.setattr(bm, "CHECK_TABLE", tmp_path / "check.md")
    monkeypatch.setattr(bm, "fetched_on", lambda: "2026-11-11")
    assert bm.main() == 0
    monkeypatch.setattr(cdb, "MARKET_DB_PATH", db)
    return db, rows


def test_build_monthly_median_cancel_dedupe(tmp_market):
    db, rows = tmp_market
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM apt_trades").fetchone()[0] == len(rows)
    assert con.execute("SELECT COUNT(DISTINCT raw_hash) FROM apt_trades").fetchone()[0] == len(rows)
    oct_ = con.execute("""SELECT median_amount, count FROM apt_trade_monthly
                          WHERE complex_id='apt:11680-218' AND area_band='60~85' AND ym='2026-10'""").fetchone()
    # 300000·320000·340000·310000·310000 + 단지명 연결 1건(300000), 해제 999000 제외
    assert oct_ == (310000.0, 6)
    sep = dict(con.execute("""SELECT area_band, count FROM apt_trade_monthly
                              WHERE complex_id='apt:11680-218' AND ym='2026-09'""").fetchall())
    assert sep == {"60~85": 1, "~60": 1}
    total = con.execute("SELECT SUM(count) FROM apt_trade_monthly").fetchone()[0]
    assert total == sum(1 for r in rows if not r["is_cancelled"])
    how = dict(con.execute("SELECT link_method, COUNT(*) FROM apt_trades GROUP BY link_method").fetchall())
    assert how == {"apt_seq": len(rows) - 1, "name": 1}
    m = dict(con.execute("SELECT key, value FROM meta").fetchall())
    assert json.loads(m["m22"]) == {"num": 1, "den": 2}
    assert json.loads(m["m23"]) == {"num": len(rows) - 1, "den": len(rows)}
    assert con.execute("SELECT COUNT(*) FROM apt_trades WHERE is_cancelled=1").fetchone()[0] == 1
    cols = {r[1] for t in ("apt_trades", "apt_complexes") for r in con.execute(f"PRAGMA table_info({t})")}
    assert not {c.lower() for c in DROP_FIELDS} & {c.lower() for c in cols}
    con.close()


def test_build_keeps_basis_columns(tmp_market):
    db, _ = tmp_market
    con = sqlite3.connect(db)
    con.execute("UPDATE apt_complexes SET kapt_code='A1', households=4424, basis_info_status='linked' WHERE id='apt:11680-218'")
    con.execute("INSERT OR REPLACE INTO meta VALUES ('list_total','236')")
    con.commit()
    con.close()
    assert bm.main() == 0
    con = sqlite3.connect(db)
    assert con.execute("SELECT kapt_code, households, basis_info_status FROM apt_complexes WHERE id='apt:11680-218'"
                       ).fetchone() == ("A1", 4424, "linked")
    assert con.execute("SELECT value FROM meta WHERE key='list_total'").fetchone()[0] == "236"
    con.close()


@pytest.fixture()
def client():
    from api.index import app
    return TestClient(app)


def test_api_shapes(tmp_market, client):
    a = client.get("/api/v1/apartments/apt:11680-218").json()
    assert a["name"] == "은마" and a["build_year"] == 1979 and a["build_year_note"] == "실거래 신고 기준"
    assert a["basis"]["status"] == "pending" and a["basis"]["label"] == "기본 정보 확인 전"
    assert a["trade_summary"]["cancelled_count"] == 1
    assert {b["band"] for b in a["trade_summary"]["bands"]} == {"60~85", "~60"}
    assert a["sources"][0]["label"] == "실거래가(국토교통부 신고 자료, 계약일 기준)"
    t = client.get("/api/v1/apartments/apt:11680-218/trades", params={"band": "60~85", "from": "2026-10"}).json()
    assert [x["ym"] for x in t["monthly"]] == ["2026-10"] and t["monthly"][0]["count"] == 6
    assert len(t["recent"]) == 7 and t["recent"][0]["is_cancelled"] in (0, 1)
    assert any(x["is_cancelled"] and x["cancelled_date"] == "2026-10-30" for x in t["recent"])
    assert {"contract_date", "amount_10k_won", "exclusive_area_m2", "floor", "is_cancelled"} <= set(t["points"][0])
    f = client.get("/api/v1/map/feature/apartment/apt:11680-218").json()
    for k in ("kind", "id", "kind_label", "title", "subtitle", "badges", "unverified", "as_of", "data_as_of", "bbox",
              "sections", "evidence", "disclaimer"):
        assert k in f
    assert f["kind"] == "apartment" and f["sections"]["apartment"]["name"] == "은마"
    assert client.get("/api/v1/apartments/apt:없음").status_code == 404
    assert client.get("/api/v1/apartments/apt:11680-218/trades?band=70").status_code == 400
    assert client.get("/api/v1/apartments/apt:11680-218/trades?from=2026-13").status_code == 400


def test_api_503_without_market_db(tmp_path, monkeypatch, client):
    monkeypatch.setattr(cdb, "MARKET_DB_PATH", tmp_path / "nope.db")
    for url in ("/api/v1/apartments/apt:11680-218", "/api/v1/apartments/apt:11680-218/trades",
                "/api/v1/map/feature/apartment/apt:11680-218"):
        r = client.get(url)
        assert r.status_code == 503 and "market.db" in r.json()["detail"]
    assert client.get("/api/v1/health").status_code == 200                       # 다른 기능은 그대로
    m = client.get("/api/v1/map/manifest")
    assert m.status_code == 200 and m.json()["market"]["available"] is False
    assert client.get("/api/v1/map/feature/project/1").status_code == 200


def test_unknown_basis_state_label():
    assert mk.BASIS_LABEL["not_in_list"] == "공동주택 기본 정보 목록에 없음"
    assert mk.BASIS_LABEL["pending"] == "기본 정보 확인 전"


# ---------- 실제 산출물 ----------

REAL_DB = ROOT / "db" / "market.db"
APT_LAYER = ROOT / "public" / "data" / "layers" / "apartments.geojson"
APT_SEED = ROOT / "seed" / "apartments.geojson"


@pytest.mark.skipif(not REAL_DB.exists(), reason="db/market.db 없음")
def test_real_api_p95(client):
    ms = []
    for _ in range(20):
        t0 = time.perf_counter()
        assert client.get("/api/v1/apartments/apt:11680-218").status_code == 200
        assert client.get("/api/v1/apartments/apt:11680-218/trades?band=60~85").status_code == 200
        ms.append((time.perf_counter() - t0) * 1000 / 2)
    assert sorted(ms)[18] <= 300


@pytest.mark.skipif(not REAL_DB.exists(), reason="db/market.db 없음")
def test_real_db_checks():
    con = sqlite3.connect(REAL_DB.as_uri() + "?mode=ro", uri=True)
    n = con.execute("SELECT COUNT(*) FROM apt_trades").fetchone()[0]
    assert con.execute("SELECT COUNT(DISTINCT raw_hash) FROM apt_trades").fetchone()[0] == n
    live_linked = con.execute("SELECT COUNT(*) FROM apt_trades WHERE is_cancelled=0 AND complex_id IS NOT NULL "
                              "AND area_band IS NOT NULL").fetchone()[0]
    assert con.execute("SELECT SUM(count) FROM apt_trade_monthly").fetchone()[0] == live_linked
    con.close()


def test_no_personal_fields_in_outputs():
    names = {f for f in DROP_FIELDS}
    for p in [APT_LAYER, APT_SEED, *(ROOT / "tests" / "fixtures" / "rtms").glob("*"), *(ROOT / "tests" / "fixtures" / "apt").glob("*")]:
        if p.exists():
            t = p.read_text(encoding="utf-8")
            assert not any(n in t for n in names), p.name


def test_no_keys_in_outputs():
    from dotenv import dotenv_values
    env = dotenv_values(ROOT / ".env") if (ROOT / ".env").exists() else {}
    keys = [v.strip() for k, v in env.items() if v and "KEY" in k and len(v.strip()) >= 12]
    if not keys:
        pytest.skip(".env 키 없음")
    forms = {f for k in keys for f in (k, quote(k, safe=""), quote_plus(k))}
    files = [APT_LAYER, APT_SEED, REAL_DB, ROOT / "public" / "data" / "layers" / "manifest.json",
             *(ROOT / "tests" / "fixtures" / "rtms").glob("*"), *(ROOT / "tests" / "fixtures" / "apt").glob("*")]
    for p in files:
        if p.exists():
            t = p.read_bytes().decode("utf-8", errors="ignore")
            assert not any(f in t for f in forms), p.name


# ---------- 기본 정보 ----------

def test_basis_not_registered_skips(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    con = sqlite3.connect(db)
    con.executescript((ROOT / "db" / "market_schema.sql").read_text(encoding="utf-8"))
    con.execute("INSERT INTO apt_complexes (id, name) VALUES ('apt:x', '은마')")
    con.commit()
    con.close()
    calls = []

    def fake_get(client, key, url, params, cache):
        calls.append(url)
        if "AptList" in url:
            return {"response": {"body": {"items": [{"kaptCode": "A1", "kaptName": "은마"}], "totalCount": 236}}}
        raise fab.NotRegistered("SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
    monkeypatch.setattr(fab, "DB", db)
    monkeypatch.setattr(fab, "get", fake_get)
    monkeypatch.setattr(fab, "_key", lambda: "x")
    monkeypatch.setattr(fab, "reopen_todo", lambda: calls.append("todo") or True)
    monkeypatch.setattr("sys.argv", ["fetch_apt_basis"])
    assert fab.main() == 0
    con = sqlite3.connect(db)
    assert con.execute("SELECT basis_info_status, kapt_code FROM apt_complexes").fetchone() == ("pending", None)
    assert dict(con.execute("SELECT key, value FROM meta").fetchall()) == {"list_total": "236",
                                                                         "basis_info_check": "not_registered"}
    con.close()
    assert "todo" in calls and len([c for c in calls if "Basis" in c]) == 1


def test_link_basis_pure(monkeypatch):
    monkeypatch.setattr(fab, "FIELD_MAP", {"households": "hh", "jibun_addr": "addr"})
    rows = [{"id": "apt:a", "name": "은마", "aliases": "[]", "pnus": '["1168010600103160000"]', "bjd_code": "1168010600"},
            {"id": "apt:b", "name": "청담자이", "aliases": "[]", "pnus": '["1168010400101340038"]', "bjd_code": "1168010400"}]
    listed = [{"kaptCode": "K1", "kaptName": "은마아파트", "bjdCode": "1168010600"},
              {"kaptCode": "K2", "kaptName": "청담 자이", "bjdCode": "1168010400"},
              {"kaptCode": "K3", "kaptName": "거래없는단지", "bjdCode": "1168010400"}]
    basis = {"K1": {"hh": 4424, "addr": "서울특별시 강남구 대치동 316 은마아파트"}, "K2": {"hh": 708, "addr": None},
             "K3": {"hh": 10, "addr": "서울특별시 강남구 청담동 1 거래없는단지"}}
    res = fab.link_basis(listed, basis, rows)
    assert res["linked"]["apt:a"]["households"] == 4424 and res["linked"]["apt:a"]["kapt_code"] == "K1"   # PNU
    assert res["linked"]["apt:b"]["kapt_code"] == "K2"                                                   # 단지명
    assert [u["kaptCode"] for u in res["unlinked"]] == ["K3"]
    assert fab.jibun_pnu("1168010400", "서울 강남구 청담동 134-38") == "1168010400101340038"
    assert fab.jibun_pnu("1168010400", "서울 강남구 청담동 산 12") == "1168010400200120000"
