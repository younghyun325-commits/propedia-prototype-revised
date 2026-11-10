"""지도 클릭 필지 조회 (docs/map/PLAN.md P15). 네트워크 없음 — 저장 응답(tests/fixtures/vworld/parcel_at_*.json)으로 돈다.

- core/live/vworld.parcel_at 파싱·강남구 밖·필지 없음·시간 초과·오류·키 없음
- core/map.parcel_at 조립 (지오코더를 부르지 않음, 좌표는 필지 경계 중심점), /api/v1/map/parcel-at·/map/parcel 형식
- lookup 리팩터링 전·후 시연 주소 15건 바이트 동일 (tests/fixtures/lookup_snapshot/, 리팩터링 전 2026-11-10에 만듦)
- 참고 구역 점 판정(core/refzones), import_reference 멱등, 지오코더 응답 저장 정리(0단계)
"""
import hashlib
import json
import shutil
import time
from datetime import date
from pathlib import Path

import pytest

from core import geo, refzones
from core import live as live_mod
from core import map as map_mod
from core.live import vworld
from core.live.http import LiveError
from core.lookup import lookup, lookup_pnu
from tests.live_fixtures import FixtureFetch

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
TODAY = date(2026, 11, 10)
YEOKSAM = (37.498701, 127.031577)          # 역삼동 823 경계 중심점 (evals/goldset/live_parcels.yaml)
PNU_YEOKSAM = "1168010100108230000"
DAECHEONG = (37.493922, 127.084139)        # 대청마을 북측구역 안 → 일원동 629-8
OUTSIDE = (37.4837, 127.0325)              # 서초구


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("VWORLD_API_KEY", "test-key")
    vworld._land_cache.clear()
    yield
    vworld._land_cache.clear()


def allowed(con):
    return {r["bjd_code"] for r in con.execute("SELECT bjd_code FROM bjd_codes")}


# ---- 3-1 parcel_at 파싱 ----
def test_parcel_at_ok(con):
    r = vworld.parcel_at(*YEOKSAM, fetch=FixtureFetch(), allowed_bjd=allowed(con))
    assert r["status"] == "ok" and r["note"] is None
    assert r["pnu"] == PNU_YEOKSAM and r["bjd_code"] == PNU_YEOKSAM[:10]
    assert r["address"] == "서울특별시 강남구 역삼동 823" and r["jibun"].startswith("823")
    assert r["boundary"]["type"] in ("Polygon", "MultiPolygon")
    c = r["centroid"]
    assert c["source"] == vworld.PARCEL_COORD_SOURCE and geo.contains(r["boundary"], c["lon"], c["lat"])


def test_parcel_at_outside(con):
    r = vworld.parcel_at(*OUTSIDE, fetch=FixtureFetch(), allowed_bjd=allowed(con))
    assert r["status"] == "outside" and r["note"] == vworld.PARCEL_OUTSIDE_NOTE and not r["pnu"].startswith("11680")


def test_parcel_at_not_found():
    r = vworld.parcel_at(37.0, 126.0, fetch=FixtureFetch())
    assert r["status"] == "not_found" and r["note"] == vworld.PARCEL_NOT_FOUND_NOTE and r["pnu"] is None


def test_parcel_at_timeout_and_errors():
    r = vworld.parcel_at(*YEOKSAM, fetch=FixtureFetch(fail_all=True))
    assert r["status"] == "timeout" and r["note"] == vworld.PARCEL_TIMEOUT_NOTE

    def http500(url, params):
        raise LiveError("HTTP 500")
    r = vworld.parcel_at(*YEOKSAM, fetch=http500)
    assert r["status"] == "unavailable" and r["note"] == vworld.PARCEL_UNAVAILABLE_NOTE and r["reason"] == "HTTP 500"
    r = vworld.parcel_at(*YEOKSAM, fetch=lambda u, p: {"response": {"status": "ERROR", "error": {"code": "X"}}})
    assert r["status"] == "unavailable"
    r = vworld.parcel_at(*YEOKSAM, fetch=FixtureFetch(), key="")
    assert r["status"] == "unavailable" and r["note"] == vworld.PARCEL_NO_KEY_NOTE


def test_parcel_at_request_params():
    f = FixtureFetch()
    vworld.parcel_at(*YEOKSAM, fetch=f)
    url, params = f.calls[0]
    assert url == vworld.DATA_URL and params["data"] == "LP_PA_CBND_BUBUN"
    assert params["geomFilter"] == "POINT(127.031577 37.498701)" and params["crs"] == "EPSG:4326"


# ---- 3-2 조립·API ----
def test_map_parcel_at_assembles_without_geocoder(con):
    f = FixtureFetch()
    r = map_mod.parcel_at(con, *YEOKSAM, live_mod.Live(f), today=TODAY)
    assert r["status"] == "ok" and r["pnu"] == PNU_YEOKSAM
    assert r["jibun_address"] == "서울특별시 강남구 역삼동 823"
    assert r["coord_source"] == vworld.PARCEL_COORD_SOURCE
    assert not any(u.endswith("/req/address") or u.endswith("/req/search") for u, _ in f.calls)   # 주소 검색·지오코더 없음
    assert set(r["layer_counts"]) == {"city", "gu", "dong", "parcel"}
    assert set(r["land"]) == set(map_mod.LAND_KEYS)
    assert r["ref_zones"] == refzones.zones_at(*YEOKSAM)


def test_map_parcel_at_daecheong_ref_zone(con):
    r = map_mod.parcel_at(con, *DAECHEONG, live_mod.Live(FixtureFetch()), today=TODAY)
    assert r["status"] == "ok" and r["pnu"] == "1168011400106290008"
    names = [z["name"] for z in r["ref_zones"]]
    assert "일원동 대청마을 북측구역" in names
    assert all(z["badge"] == "참고·비상업" and z["source"] and z["license"] for z in r["ref_zones"])
    projects = [p["project_id"] for p in r["included_projects"] + r["nearby_projects"]]
    moa = con.execute("SELECT id FROM projects WHERE project_type='moa_town'").fetchone()["id"]
    assert moa in projects


def test_map_parcel_outside_and_offline(con):
    r = map_mod.parcel_at(con, *OUTSIDE, live_mod.Live(FixtureFetch()))
    assert r["status"] == "outside" and r["layer_counts"] is None and r["land"] is None
    r = map_mod.parcel_at(con, *YEOKSAM, None)
    assert r["status"] == "unavailable" and r["message"] == map_mod.LIVE_OFF_NOTE


def test_api_parcel_at(client, monkeypatch):
    import api.index as api
    r = client.get("/api/v1/map/parcel-at", params={"lat": YEOKSAM[0], "lon": YEOKSAM[1]})
    assert r.status_code == 200 and r.json()["status"] == "unavailable"          # pytest: PROPEDIA_LIVE=0
    assert client.get("/api/v1/map/parcel-at", params={"lat": 35.1, "lon": 129.0}).status_code == 400
    assert client.get("/api/v1/map/parcel", params={"pnu": "123"}).status_code == 400
    monkeypatch.setattr(api.live_mod, "default", lambda: live_mod.Live(FixtureFetch()))
    d = client.get("/api/v1/map/parcel-at", params={"lat": YEOKSAM[0], "lon": YEOKSAM[1]}).json()
    keys = {"status", "message", "pnu", "jibun_address", "boundary", "centroid", "land", "building", "building_note",
            "layer_counts", "included_projects", "nearby_projects", "nearby_note", "ref_zones", "as_of", "disclaimer"}
    assert keys <= set(d) and d["status"] == "ok" and d["pnu"] == PNU_YEOKSAM
    d2 = client.get("/api/v1/map/parcel", params={"pnu": PNU_YEOKSAM}).json()
    assert d2["status"] == "ok" and d2["pnu"] == PNU_YEOKSAM and d2["boundary"] == d["boundary"]


# ---- lookup 리팩터링 전·후 동일 ----
def test_lookup_snapshot_bytes_same(con):
    rows = con.execute("SELECT addr_id, input_text FROM demo_addresses ORDER BY addr_id").fetchall()
    assert len(rows) == 15
    for r in rows:
        got = json.dumps(lookup(con, r["input_text"], today=TODAY), ensure_ascii=False, sort_keys=True) + "\n"
        want = (FIX / "lookup_snapshot" / f"{r['addr_id']}.json").read_text(encoding="utf-8")
        assert got == want, r["addr_id"]


def test_lookup_pnu_same_layers_as_lookup(con):
    for aid in ("A1", "B1", "A8"):
        row = con.execute("SELECT input_text, pnu FROM demo_addresses WHERE addr_id=?", (aid,)).fetchone()
        a = lookup(con, row["input_text"], today=TODAY)
        b = lookup_pnu(con, row["pnu"], today=TODAY)
        assert a["layers"] == b["layers"] and a["reference"] == b["reference"], aid
    assert lookup_pnu(con, "1165010800113760003")["status"] == "out_of_scope"


# ---- 참고 구역 점 판정 ----
def _ref_feature(name):
    fc = json.loads((map_mod.LAYERS_DIR / "ref_seoulplan.geojson").read_text(encoding="utf-8"))
    return next(f for f in fc["features"] if f["properties"]["DGM_NM"] == name)


@pytest.mark.parametrize("name", ["일원동 대청마을 북측구역", "대치선경"])
def test_refzones_inside_outside(name):
    f = _ref_feature(name)
    lon, lat = geo.centroid(f["geometry"])
    assert name in [z["name"] for z in refzones.zones_at(lat, lon)]
    w, s, e, n = geo.bbox(f["geometry"])
    assert name not in [z["name"] for z in refzones.zones_at(n + 0.002, e + 0.002)]     # 바깥 점


def test_refzones_speed():
    refzones.zones_at(*YEOKSAM)                     # 첫 읽기
    t = time.perf_counter()
    for _ in range(200):
        refzones.zones_at(*DAECHEONG)
    assert (time.perf_counter() - t) / 200 * 1000 < 10          # ms


def test_geo_contains_hole():
    g = {"type": "Polygon", "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
                                            [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]]}
    assert geo.contains(g, 0.5, 0.5) and not geo.contains(g, 2, 2) and not geo.contains(g, 5, 5)


# ---- import_reference 멱등 ----
def test_import_reference_idempotent(tmp_path, monkeypatch):
    from pipeline import common
    if not (common.SHP_SEOULPLAN.exists() and common.SHP_UIJE.exists()):
        pytest.skip("data_raw/11.공간정보 SHP 없음")
    from pipeline import import_reference as ir
    shutil.copy(map_mod.LAYERS_DIR / "manifest.json", tmp_path / "manifest.json")
    monkeypatch.setattr(ir, "OUT", tmp_path)
    monkeypatch.setattr(ir, "BUILD", tmp_path / "build")

    def digest():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(tmp_path.glob("*.*"))}
    ir.main()
    one = digest()
    ir.main()
    assert digest() == one
    for name in ("ref_seoulplan.geojson", "ref_uije.geojson", "manifest.json"):     # 커밋된 결과와도 같다
        # git autocrlf로 작업 사본이 CRLF가 될 수 있어 줄끝만 맞춰 비교 (빌드 출력은 LF)
        committed = (map_mod.LAYERS_DIR / name).read_bytes().replace(b"\r\n", b"\n")
        assert one[name] == hashlib.sha256(committed).hexdigest(), name


def test_reference_geojson_keeps_original_fields():
    fc = json.loads((map_mod.LAYERS_DIR / "ref_uije.geojson").read_text(encoding="utf-8"))
    p = fc["features"][0]["properties"]
    assert {"PRESENT_SN", "LCLAS_CL", "ATRB_SE", "DGM_NM", "DGM_AR", "SIGNGU_SE", "CREATE_DAT"} <= set(p)
    assert {k for k in p if k.startswith("_")} == {"_source", "_license", "_as_of", "_ref", "_layer", "_row"}


# ---- 0단계: 지오코더 응답 저장 정리 ----
def test_geocoder_fixtures_are_samples():
    for name in ("getcoord_527.json", "getcoord_1168011400106190000.json", "search_road_teheran_427.json"):
        j = json.loads((FIX / "vworld" / name).read_text(encoding="utf-8"))
        assert "_sample_note" in j, name
        resp = j["response"]
        points = [resp["result"]["point"]] if "point" in resp["result"] else [it["point"] for it in resp["result"]["items"]]
        assert all(pt == {"x": "127.000000", "y": "37.500000"} for pt in points), name


def test_check_keys_never_saves_geocoder_body():
    src = (ROOT / "pipeline" / "check_keys.py").read_text(encoding="utf-8")
    for line in src.splitlines():
        if "save(" in line:
            assert "getcoord" not in line and "search_road" not in line, line


def test_parcel_fixtures_have_no_key_or_domain():
    env = ROOT / ".env"
    vals = ["propedia-pretotype.vercel.app", "localhost:3000"]
    if env.exists():
        vals += [ln.split("=", 1)[1].strip().strip('"') for ln in env.read_text(encoding="utf-8").splitlines()
                 if "=" in ln and not ln.lstrip().startswith("#")]
    vals = [v for v in vals if len(v) > 8]
    for f in (FIX / "vworld").glob("parcel_at_*.json"):
        text = f.read_text(encoding="utf-8")
        assert not any(v in text for v in vals), f.name


# ---- 참고 WMS 타일 프록시 (브이월드 WMS에 CORS 헤더가 없음) ----
class FakeBytes:
    def __init__(self, ctype="image/png", fail=None):
        self.calls, self.ctype, self.fail = [], ctype, fail

    def __call__(self, url, params):
        self.calls.append((url, dict(params)))
        if self.fail:
            raise LiveError(self.fail)
        return b"\x89PNG-test", self.ctype


def test_wms_tile_params_and_size():
    f = FakeBytes()
    r = vworld.wms_tile("lp_pa_cbnd_bubun", 17, 111695, 50822, fetch_bytes=f, key="k")
    assert r["status"] == "ok" and r["content"] == b"\x89PNG-test" and r["content_type"] == "image/png"
    url, p = f.calls[0]
    assert url == vworld.WMS_URL and p["LAYERS"] == p["STYLES"] == "lp_pa_cbnd_bubun" and p["CRS"] == "EPSG:3857"
    assert p["WIDTH"] == p["HEIGHT"] == 512                       # 0.6m/px 이하로 받기 (줌 17 = 1.19m/px × 256)
    w, s, e, n = (float(v) for v in p["BBOX"].split(","))
    assert abs((e - w) - 2 * vworld._R3857 / 2 ** 17) < 1e-6 and n > s
    assert vworld.wms_size("lp_pa_cbnd_bubun", 18) == 256 and vworld.wms_size("lt_c_uq111", 14) == 256


def test_wms_tile_rejects_and_failures():
    f = FakeBytes()
    assert vworld.wms_tile("lt_c_evil", 15, 0, 0, fetch_bytes=f, key="k")["status"] == "bad_request"
    assert vworld.wms_tile("lp_pa_cbnd_bubun", 16, 0, 0, fetch_bytes=f, key="k")["status"] == "bad_request"
    assert vworld.wms_tile("lt_c_uq111", 14, 2 ** 14, 0, fetch_bytes=f, key="k")["status"] == "bad_request"
    assert f.calls == []
    assert vworld.wms_tile("lt_c_uq111", 14, 1, 1, fetch_bytes=FakeBytes(fail="TimeoutError"), key="k")["status"] == "timeout"
    assert vworld.wms_tile("lt_c_uq111", 14, 1, 1, fetch_bytes=FakeBytes(ctype="application/xml"), key="k")["status"] \
        == "unavailable"
    assert vworld.wms_tile("lt_c_uq111", 14, 1, 1, fetch_bytes=FakeBytes(), key="")["status"] == "unavailable"


def test_api_wms_tile(client, monkeypatch):
    import api.index as api
    assert client.get("/api/v1/map/wms/lt_c_uq111/14/13974/6348.png").status_code == 503      # PROPEDIA_LIVE=0

    class FakeLive:
        def wms_tile(self, layer, z, x, y, size=None):
            return vworld.wms_tile(layer, z, x, y, size=size, fetch_bytes=FakeBytes(), key="k")
    monkeypatch.setattr(api.live_mod, "default", lambda: FakeLive())
    r = client.get("/api/v1/map/wms/lt_c_uq111/14/13974/6348.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and "max-age" in r.headers["cache-control"]
    assert client.get("/api/v1/map/wms/evil/14/1/1.png").status_code == 400
