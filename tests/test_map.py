"""지도 API (docs/map/PLAN.md P14): manifest·notices·projects·health 키 상태, within_impact.

건수는 숫자로 적지 않고 서버가 읽는 data/server/layers/manifest.json·GeoJSON·DB에서 읽어 비교한다 (P20-B: core/paths.py).
"""
import json
import os
from datetime import date

from core import map as map_mod
from core.live.http import env_key
from core.paths import layers_dir
from core.progress import progress

ROOT = map_mod.ROOT
FIX = ROOT / "tests" / "fixtures" / "map_manifest.json"
LAYER_KEYS = {"id", "group", "name", "kind", "source", "license", "as_of", "count", "status", "note", "available_from"}
STATUSES = {"ready", "pending", "not_adopted"}
KINDS = {"fill", "line", "symbol", "raster"}


def _manifest_file() -> dict:
    return json.loads((layers_dir() / "manifest.json").read_text(encoding="utf-8"))


def _fc(name: str) -> list[dict]:
    return json.loads((layers_dir() / f"{name}.geojson").read_text(encoding="utf-8"))["features"]


def test_manifest_shape_matches_fixture(client):
    r = client.get("/api/v1/map/manifest")
    assert r.status_code == 200
    d = r.json()
    fx = json.loads(FIX.read_text(encoding="utf-8"))
    assert set(d) == set(fx) - {"_note"}
    assert [x["id"] for x in d["layers"]] == [x["id"] for x in fx["layers"]]
    for got, want in zip(d["layers"], fx["layers"]):
        assert set(got) == set(want), got["id"]
        assert LAYER_KEYS <= set(got)
        assert got["status"] in STATUSES and got["kind"] in KINDS


def test_manifest_counts_from_files_and_db(client, con):
    d = {x["id"]: x for x in client.get("/api/v1/map/manifest").json()["layers"]}
    m = _manifest_file()["layers"]
    assert d["projects"]["count"] == m["propedia_projects"]["count"]
    assert d["parcels"]["count"] == m["propedia_parcels"]["count"]
    assert d["regulations"]["count"] == m["propedia_regulations"]["count"]
    imp = _fc("propedia_impact")
    assert d["impact250"]["count"] + d["impact500"]["count"] == m["propedia_impact"]["count"] == len(imp)
    # 판정별 건수 = DB, 합 = 필지 레이어 건수
    by = d["parcels"]["count_by_judgment"]
    assert set(by) == {"included", "possible", "likely"}
    assert by == map_mod.parcel_judgments(con)
    assert sum(by.values()) == d["parcels"]["count"]
    assert by["likely"] == sum(1 for f in _fc("propedia_parcels") if f["properties"]["inclusion"] == "likely")


def test_manifest_status(client):
    d = {x["id"]: x for x in client.get("/api/v1/map/manifest").json()["layers"]}
    assert d["regulation-d5"]["status"] == "not_adopted"
    assert d["regulation-d5"]["note"] == "경계 확인 전, 법정동(압구정동) 단위로만 표시"
    # P18 생활 인프라 4종: pipeline/fetch_pois.py manifest 항목이 있으면 ready (준비 중 레이어는 더 없음)
    assert not [x for x in d.values() if x["status"] == "pending"]
    assert {lid: d[lid]["default_on"] for lid in ("schools", "stations", "bus_stops", "pois")} ==         {"schools": True, "stations": True, "bus_stops": False, "pois": False}
    assert (d["bus_stops"]["min_zoom"], d["bus_stops"]["label_min_zoom"]) == (15, 17)
    assert d["bus_stops"]["routes"]["file"] == "bus_routes.json" and len(d["pois"]["categories"]) == 6
    for lid in ("basemap-gray", "projects", "impact250", "impact500", "parcels", "regulations",
                "ref-seoulplan", "ref-uije", "ref-zoning", "ref-district", "ref-cadastral", "apartments",
                "schools", "stations", "bus_stops", "pois"):
        assert d[lid]["status"] == "ready", lid


def test_manifest_reference_layers(client):
    """P15 공식 참고: 빌드 GeoJSON 2종은 manifest.json ref_* 항목 그대로, WMS 3종은 Capabilities로 확인한 이름."""
    d = {x["id"]: x for x in client.get("/api/v1/map/manifest").json()["layers"]}
    man = _manifest_file()["layers"]
    for lid, key in (("ref-seoulplan", "ref_seoulplan"), ("ref-uije", "ref_uije")):
        assert d[lid]["group"] == "reference" and d[lid]["lazy"] is True and d[lid]["badge"] == "참고·비상업"
        assert d[lid]["count"] == man[key]["count"] == len(_fc(key))
        assert "4유형" in d[lid]["license"] and d[lid]["file"] == f"{key}.geojson"
    assert {k for k in man if k.startswith("propedia_")} and {k for k in man if k.startswith("ref_")}
    assert {lid: (d[lid]["wms_layer"], d[lid]["min_zoom"]) for lid in ("ref-zoning", "ref-district", "ref-cadastral")}         == {"ref-zoning": ("lt_c_uq111", 14), "ref-district": ("lt_c_upisuq161", 14),
            "ref-cadastral": ("lp_pa_cbnd_bubun", 17)}


def test_manifest_503(client, monkeypatch, tmp_path):
    monkeypatch.setattr(map_mod, "_layers_dir", lambda: tmp_path)
    r = client.get("/api/v1/map/manifest")
    assert r.status_code == 503
    assert "manifest.json" in r.json()["detail"]


def test_notices_as_of(client):
    a = client.get("/api/v1/map/notices", params={"as_of": "2026-11-10"}).json()
    assert a["as_of"] == "2026-11-10"
    assert [x["doc_id"] for x in a["items"]] == ["D6", "D7", "D8"]
    d6 = a["items"][0]
    assert d6["effective_to"] == "2026-12-31" and d6["effective_label"] == "효력 기간 2025.10.20 ~ 2026.12.31"
    assert d6["source"]["pdf_page"] and d6["source"]["page_image"]
    assert {"doc_id", "short_title", "doc_kind", "kind_label", "effective_label", "source"} <= set(d6)
    # D6 효력 종료(2026-12-31) 다음 날에는 빠진다
    b = client.get("/api/v1/map/notices", params={"as_of": "2027-01-01"}).json()
    assert [x["doc_id"] for x in b["items"]] == ["D7", "D8"]
    assert client.get("/api/v1/map/notices", params={"as_of": "2026-13-01"}).status_code == 400


def test_notices_regulation_scope(client):
    """P20: 규제마다 적용 범위와 지도 도형 유무 — 도형이 없으면 화면이 법정동·구 경계로 대신 강조한다"""
    regs = {r["doc_id"]: r for r in client.get("/api/v1/map/notices", params={"as_of": "2026-11-10"}).json()["regulations"]}
    assert regs["D10"]["has_geometry"] is True and regs["D10"]["scope_type"] == "BJD"
    assert regs["D5"]["has_geometry"] is False
    assert regs["D5"]["scope_type"] == "BJD" and regs["D5"]["scope_ref"] == ["1168011000"]
    for d in ("D6", "D7", "D8"):
        assert regs[d]["has_geometry"] is False and regs[d]["scope_type"] == "SIDO" and regs[d]["scope_ref"] == ["11"]


def test_notices_default_today(client):
    assert client.get("/api/v1/map/notices").status_code == 200


def test_projects_match_progress(client, con):
    day = date(2026, 11, 10)
    d = client.get("/api/v1/map/projects", params={"as_of": day.isoformat()}).json()
    assert d["as_of"] == "2026-11-10"
    n = con.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    assert len(d["projects"]) == n
    for p in d["projects"]:
        pr = progress(con, p["id"], today=day)
        api_pr = client.get(f"/api/v1/projects/{p['id']}/progress").json()
        assert p["position_label"] == pr["position_label"] == api_pr["position_label"]
        assert p["name"] == pr["name"] == api_pr["name"]
        cur = next(s for s in pr["stages"] if s["status"] == "current")
        assert (p["stage_seq"], p["stage_total"], p["stage_title"]) == (cur["seq"], len(pr["stages"]), cur["title"])
        dl = pr["deadlines"][0]
        assert p["deadline"]["d_day_label"] == dl["d_day_label"] and p["deadline"]["status"] == dl["status"]
        assert p["status_badge"] == (pr["sub_status"] or pr["current"]["title"])
        assert len(p["bbox"]) == 4 and p["bbox"][0] < p["bbox"][2] and p["bbox"][1] < p["bbox"][3]
        rows = con.execute("SELECT COUNT(*), SUM(verified=0) FROM project_parcels WHERE project_id=?",
                           (p["id"],)).fetchone()
        assert sum(p["parcels"].values()) == rows[0]
        assert p["unverified"] is True and p["parcels_unverified"] == rows[1]
        assert p["hover_line"].startswith(p["short_name"])
    hy = next(p for p in d["projects"] if p["id"] == 1)
    assert hy["deadline"]["d_day_label"] == "마감(2026.11.06)"
    assert hy["hover_line"] == "한양7차아파트 재건축 · 2/13단계 · 정비계획(안) 주민공람 마감"
    # 공람 기간 중 기준일이면 D-n
    e = client.get("/api/v1/map/projects", params={"as_of": "2026-10-25"}).json()
    assert next(p for p in e["projects"] if p["id"] == 1)["deadline"]["d_day_label"] == "D-12"


def test_within_impact(con):
    """필지마다 중심점이 자기 사업의 250m 영향권 안 (528 포함), D10 규제 구역은 영향권 밖."""
    parcels = _fc("propedia_parcels")
    assert len(parcels) == _manifest_file()["layers"]["propedia_parcels"]["count"]
    db = {(r["project_id"], r["pnu"]) for r in con.execute("SELECT project_id, pnu FROM project_parcels")}
    assert {(f["properties"]["project_id"], f["properties"]["pnu"]) for f in parcels} == db
    expected = {f["properties"]["id"]: {"project_id": f["properties"]["project_id"], "buffer_m": 250} for f in parcels}
    got = {f["properties"]["id"]: f["properties"]["within_impact"] for f in parcels}
    assert got == expected
    assert got["parcel:1:1168011000105280000"] == {"project_id": 1, "buffer_m": 250}
    for f in parcels:
        assert f["properties"]["impact_buffer_m"] == f["properties"]["within_impact"]["buffer_m"]
    regs = {f["properties"]["id"]: f["properties"] for f in _fc("propedia_regulations")}
    assert regs["regulation:D10"]["within_impact"] == {"project_id": None, "buffer_m": None}
    assert regs["regulation:D10"]["impact_buffer_m"] is None


def test_health_key_status_without_values(client):
    r = client.get("/api/v1/health")
    h = r.json()
    assert set(h["keys"]) == {"vworld", "juso"}
    assert set(h["keys"].values()) <= {"있음", "없음"}
    text = r.text
    for name in ("VWORLD_API_KEY", "JUSO_CONFM_KEY", "JUSO_CONFM_KEY_ALT", "VITE_VWORLD_KEY", "VWORLD_API_KEY_DEV",
                 "DATA_GO_KR_SERVICE_KEY"):
        v = env_key(name) or (os.environ.get(name) or "").strip()
        if len(v) >= 6:
            assert v not in text, f"{name} 값이 응답에 들어 있음"
