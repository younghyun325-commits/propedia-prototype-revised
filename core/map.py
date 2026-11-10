"""지도 화면용 조회 (docs/map/PLAN.md P14). 표준 라이브러리만, DB는 읽기 전용, 네트워크 없음.

- map_manifest: public/data/layers/manifest.json + public/data/base/ 를 읽어 레이어 목록(아직 없는 레이어는 pending)
- map_notices: 지도에 영역이 없는 서울 전역·강남구 단위 고시 (상단 바 칩). 효력 판정은 lookup.load_items 그대로
- map_projects: 사업 목록. 단계·기한은 progress() 결과를 그대로 쓰고 새로 계산하지 않는다
- key_status: 실시간 조회 키가 있는지 '있음/없음'만 (값은 절대 내보내지 않음)
- parcel_at / parcel_by_pnu: 지도 클릭 필지 조회 (P15). 필지 찾기는 core/live(브이월드 2D 데이터), 나머지는
  lookup_pnu(기존 4개 층 조립)·refzones(공식 참고 구역 점 판정)를 그대로 쓴다. 결과는 저장하지 않는다.
건수는 여기·화면·테스트 어디에도 숫자로 적지 않고 manifest·GeoJSON·DB에서 읽는다.
"""
import json
from pathlib import Path

from core.catalog import DOC_KIND_LABELS
from core.db import meta
from core import refzones
from core.lookup import DISCLAIMER, load_items, lookup_pnu
from core.progress import progress
from core.review import Overrides

ROOT = Path(__file__).resolve().parents[1]
LAYERS_DIR = ROOT / "public" / "data" / "layers"
BASE_DIR = ROOT / "public" / "data" / "base"
SGG_GANGNAM = "11680"

# 포함 판정 (pipeline/build_map_layers.py도 이 표를 쓴다: 한 곳에서만 정의)
INCLUSION = {"representative_only": "possible", "map_reading": "likely", "manual_review": "included",
             "jibun_table": "included"}
INCLUSION_LABEL = {"included": "포함", "possible": "포함될 수 있음", "likely": "포함된 것으로 보임 (확인 필요)"}
JUDGMENTS = ("included", "possible", "likely")

UNAVAILABLE = "지도 레이어 목록 파일(public/data/layers/manifest.json)을 읽지 못했습니다. pipeline.build_map_layers를 먼저 실행해 주세요"
VWORLD_SRC = "브이월드 WMTS (국토교통부)"
VWORLD_LICENSE = "공공누리 1유형 (출처표시)"
D5_NOTE = "경계 확인 전, 법정동(압구정동) 단위로만 표시"
IMPACT_NOTE = "영향권 250m·500m는 Propedia 표시 기준이며 영향의 크기를 뜻하지 않습니다"
UNVERIFIED_NOTE = "사람 확인 전"

GROUPS = [
    {"id": "basemap", "name": "배경지도"},
    {"id": "propedia", "name": "Propedia 고시·사업"},
    {"id": "reference", "name": "공식 참고"},
    {"id": "market", "name": "시장"},
    {"id": "infra", "name": "생활 인프라"},
    {"id": "base", "name": "기본 경계"},
]

# 공식 참고 레이어 (P15). 빌드 GeoJSON 2종은 manifest.json의 ref_* 항목(pipeline/import_reference.py),
# WMS 3종은 브이월드 GetCapabilities로 확인한 이름 (pipeline/check_wms.py, 2026-11-10: GetLegendGraphic 없음 → 범례 없음).
# 브이월드 WMS는 CORS 헤더가 없어 화면은 /api/v1/map/wms/{layer}/{z}/{x}/{y}.png(서버 키 프록시)로 받는다
REF_GEOJSON = [("ref-seoulplan", "ref_seoulplan", "서울시 도시계획사업 현황"), ("ref-uije", "ref_uije", "의제처리구역")]
REF_WMS = [
    {"id": "ref-zoning", "name": "용도지역 (WMS)", "wms_layer": "lt_c_uq111", "wms_title": "도시지역", "min_zoom": 14},
    {"id": "ref-district", "name": "지구단위계획구역 (WMS)", "wms_layer": "lt_c_upisuq161", "wms_title": "지구단위계획",
     "min_zoom": 14},
    # 연속지적도 WMS는 0.6m/px보다 거친 요청에 빈 그림을 준다 → 줌 17부터 (core/live/vworld.WMS_MAX_MPP)
    {"id": "ref-cadastral", "name": "지적도 (WMS)", "wms_layer": "lp_pa_cbnd_bubun", "wms_title": "연속지적도",
     "min_zoom": 17},
]
WMS_BADGE = "참고"

# 아직 데이터가 없는 레이어 (P17·P18에서 채움)
PENDING = [
    {"id": "apartments", "group": "market", "name": "아파트 단지", "kind": "fill",
     "source": "국토교통부 공동주택 단지 목록·기본 정보", "license": "이용허락범위 제한 없음", "available_from": "P17"},
    {"id": "schools", "group": "infra", "name": "학교", "kind": "symbol",
     "source": "전국초중등학교위치표준데이터", "license": "이용허락범위 제한 없음", "available_from": "P18"},
    {"id": "subway", "group": "infra", "name": "지하철역", "kind": "symbol",
     "source": "서울시 역사마스터 정보", "license": "출처표시", "available_from": "P18"},
    {"id": "amenities", "group": "infra", "name": "편의시설", "kind": "symbol",
     "source": "소상공인시장진흥공단 상가(상권)정보", "license": "이용허락범위 제한 없음", "available_from": "P18"},
]

BASEMAPS = [("basemap-base", "기본"), ("basemap-gray", "회색"), ("basemap-satellite", "위성"),
            ("basemap-hybrid", "하이브리드")]


class MapDataUnavailable(Exception):
    """manifest.json을 읽지 못함 → API 503"""


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _features(name: str) -> list[dict]:
    fc = _read_json(LAYERS_DIR / f"{name}.geojson")
    return (fc or {}).get("features") or []


def _source_pages(name: str) -> list[str]:
    """도형 속성의 근거 쪽 (예: 'D1 p18'). 문서 순서·쪽 순서로 정렬"""
    def norm(s: str) -> str:            # 'D10 p03' → 'D10 p3'
        doc, _, pg = s.partition(" p")
        return f"{doc} p{int(pg)}" if pg.isdigit() else s

    def key(s: str):
        doc, _, pg = s.partition(" p")
        return (int(doc[1:]) if doc[1:].isdigit() else 999, int(pg) if pg.isdigit() else 0)
    return sorted({norm(f["properties"]["source_page"]) for f in _features(name)
                   if f["properties"].get("source_page")}, key=key)


def _unverified(m: dict) -> bool:
    return "verified=0" in (m.get("verified") or "")


def parcel_judgments(con) -> dict:
    """포함 판정별 필지 수 (DB project_parcels). verified=1이면 basis와 상관없이 포함."""
    out = {j: 0 for j in JUDGMENTS}
    for r in con.execute("SELECT basis, verified FROM project_parcels"):
        out["included" if r["verified"] else INCLUSION.get(r["basis"], "possible")] += 1
    return out


def map_manifest(con) -> dict:
    man = _read_json(LAYERS_DIR / "manifest.json")
    if not man or not isinstance(man.get("layers"), dict):
        raise MapDataUnavailable(UNAVAILABLE)
    L = man["layers"]
    m = meta(con)
    layers: list[dict] = []

    def entry(id_, group, name, kind, src: dict | None, *, count=None, status="ready", note=None, **extra):
        src = src or {}
        layers.append({"id": id_, "group": group, "name": name, "kind": kind, "source": src.get("source"),
                       "license": src.get("license"), "as_of": src.get("as_of"),
                       "count": src.get("count") if count is None else count, "status": status, "note": note,
                       "available_from": None, "unverified": _unverified(src), "doc_ids": src.get("doc_ids", []),
                       "source_pages": src.get("source_pages", []), **extra})

    for id_, name in BASEMAPS:
        entry(id_, "basemap", name, "raster", {"source": VWORLD_SRC, "license": VWORLD_LICENSE})

    pj = L.get("propedia_projects")
    if pj:
        pj = pj | {"source_pages": _source_pages("propedia_projects")}
    entry("projects", "propedia", "사업 구역", "fill", pj, status="ready" if pj else "pending")
    im = L.get("propedia_impact")
    imp = _features("propedia_impact")
    if im:
        im = im | {"source_pages": _source_pages("propedia_impact")}
    for b in (250, 500):
        entry(f"impact{b}", "propedia", f"영향권 {b}m", "fill", im,
              count=sum(1 for f in imp if f["properties"].get("buffer_m") == b),
              status="ready" if im else "pending", note=IMPACT_NOTE)
    pa = L.get("propedia_parcels")
    if pa:
        pa = pa | {"source_pages": _source_pages("propedia_parcels")}
    entry("parcels", "propedia", "포함 판정 필지", "line", pa, status="ready" if pa else "pending",
          count_by_judgment=parcel_judgments(con),
          unverified_count=con.execute("SELECT COUNT(*) FROM project_parcels WHERE verified=0").fetchone()[0])
    rg = L.get("propedia_regulations")
    if rg:
        rg = rg | {"source_pages": _source_pages("propedia_regulations")}
    entry("regulations", "propedia", "규제 구역", "fill", rg, status="ready" if rg else "pending")
    d5 = next((n for n in man.get("notes") or [] if n.startswith("D5")), None)
    if d5:
        entry("regulation-d5", "propedia", "압구정 아파트지구 토지거래허가구역 (D5)", "fill",
              {"source": "서울특별시 공고 제2026-1141호 지형도면", "doc_ids": ["D5"]}, count=0,
              status="not_adopted", note=d5.split(":", 1)[1].strip() if ":" in d5 else D5_NOTE)

    for id_, key, name in REF_GEOJSON:
        rf = L.get(key)
        entry(id_, "reference", name, "fill", rf, status="ready" if rf else "pending",
              note=(rf or {}).get("note") or "pipeline.import_reference 실행 전", badge=(rf or {}).get("badge"),
              lazy=True, file=(rf or {}).get("file"), size_bytes=(rf or {}).get("size_bytes"),
              disclaimer=(rf or {}).get("disclaimer"), ref=True)
    for w in REF_WMS:
        entry(w["id"], "reference", w["name"], "raster",
              {"source": f"브이월드 WMS {w['wms_layer']} ({w['wms_title']})", "license": VWORLD_LICENSE},
              status="ready", note=None, badge=WMS_BADGE, wms_layer=w["wms_layer"], min_zoom=w["min_zoom"],
              tile_url=f"/api/v1/map/wms/{w['wms_layer']}/{{z}}/{{x}}/{{y}}.png",
              legend_url=None, ref=True)

    for p in PENDING:
        layers.append({"id": p["id"], "group": p["group"], "name": p["name"], "kind": p["kind"], "source": p["source"],
                       "license": p["license"], "as_of": None, "count": None, "status": "pending",
                       "note": f"{p['available_from']} 준비 중", "available_from": p["available_from"],
                       "unverified": False, "doc_ids": [], "source_pages": [], **({"badge": p["badge"]} if p.get("badge") else {})})

    for id_, name, fn in (("boundary-gangnam", "강남구 경계", "gangnam"), ("boundary-bjd", "법정동 경계", "bjd")):
        fc = _read_json(BASE_DIR / f"{fn}.geojson")
        entry(id_, "base", name, "line",
              {"source": "브이월드 2D 데이터 (국토교통부)", "license": VWORLD_LICENSE,
               "count": len(fc["features"]) if fc else None}, status="ready" if fc else "pending")

    return {"generated_as_of": man.get("generated_as_of"), "db_as_of": m.get("as_of"), "build_at": m.get("build_at"),
            "crs": man.get("crs"), "groups": GROUPS, "layers": layers, "notes": man.get("notes") or []}


def map_notices(con, today) -> dict:
    """지도에 영역이 없는 서울 전역·강남구 단위 고시 중 기준일에 효력 중인 것 (계획 문서는 뺀다)."""
    kinds = {r["doc_id"]: r["doc_kind"] for r in con.execute("SELECT doc_id, doc_kind FROM documents")}
    out = []
    for it in load_items(con, Overrides(), today):
        refs = it["scope_ref"]
        wide = (it["scope_type"] == "SIDO" and "11" in refs) or (it["scope_type"] == "SGG" and SGG_GANGNAM in refs)
        doc = (it["source"] or {}).get("doc_id")
        kind = kinds.get(doc)
        if not wide or it["tier"] != "applies" or kind in (None, "plan"):
            continue
        if it["effective_status"] in ("ended", "not_started"):
            continue
        out.append({"doc_id": doc, "item_key": it["item_key"], "short_title": it["source"]["short_title"],
                    "title": it["title"], "doc_kind": kind, "kind_label": DOC_KIND_LABELS.get(kind, kind),
                    "effective_from": it["effective_from"], "effective_to": it["effective_to"],
                    "effective_label": it["effective_label"], "effective_status_label": it["effective_status_label"],
                    "target_note": it["target_note"], "source": it["source"]})
    out.sort(key=lambda x: (int(x["doc_id"][1:]) if x["doc_id"][1:].isdigit() else 999, x["item_key"]))
    return {"as_of": today.isoformat(), "items": out}


def _bbox(geom: dict) -> list[float] | None:
    w = s = 999.0
    e = n = -999.0
    stack = [geom.get("coordinates")]
    while stack:
        c = stack.pop()
        if not c:
            continue
        if isinstance(c[0], (int, float)):
            w, e, s, n = min(w, c[0]), max(e, c[0]), min(s, c[1]), max(n, c[1])
        else:
            stack.extend(c)
    return [round(w, 6), round(s, 6), round(e, 6), round(n, 6)] if w <= e else None


def map_projects(con, today) -> dict:
    geoms = {f["properties"]["id"]: f for f in _features("propedia_projects")}
    out = []
    for p in con.execute("SELECT id FROM projects ORDER BY id").fetchall():
        pr = progress(con, p["id"], today=today)
        stages = pr["stages"]
        cur = next(s for s in stages if s["status"] == "current")
        aliases = pr["aliases"]
        short = aliases[0] if aliases else pr["name"]
        dl = pr["deadlines"][0] if pr["deadlines"] else None
        deadline = None
        if dl:
            deadline = {"title": dl["title"], "starts_on": dl["starts_on"], "due_on": dl["due_on"],
                        "d_day": dl["d_day"], "d_day_label": dl["d_day_label"], "status": dl["status"]}
        counts = {j: 0 for j in JUDGMENTS}
        unverified = 0
        for r in con.execute("SELECT basis, verified FROM project_parcels WHERE project_id=?", (p["id"],)):
            counts["included" if r["verified"] else INCLUSION.get(r["basis"], "possible")] += 1
            unverified += 0 if r["verified"] else 1
        rep = con.execute("""SELECT pnu FROM project_parcels WHERE project_id=? AND basis='representative_only'
                             ORDER BY pnu LIMIT 1""", (p["id"],)).fetchone()
        g = geoms.get(f"project:{p['id']}")
        gp = (g or {}).get("properties", {})
        status_badge = pr["sub_status"] or pr["current"]["title"]
        dl_part = None
        if deadline:
            dl_part = (f"{deadline['title']} 마감" if deadline["status"] == "closed"
                       else f"{deadline['title']} {deadline['d_day_label']}")
        hover = " · ".join(x for x in [short, f"{cur['seq']}/{len(stages)}단계", dl_part] if x)
        out.append({
            "id": pr["project_id"], "feature_id": f"project:{pr['project_id']}", "name": pr["name"],
            "short_name": short, "aliases": aliases, "project_type": pr["project_type"],
            "project_type_label": pr["project_type_label"], "position_label": pr["position_label"],
            "stage_seq": cur["seq"], "stage_total": len(stages), "stage_title": cur["title"],
            "status_badge": status_badge, "stage_note": pr["stage_note"], "deadline": deadline,
            "representative_jibun": pr["location_text"], "representative_pnu": rep["pnu"] if rep else None,
            "bbox": _bbox(g["geometry"]) if g else None, "has_boundary": g is not None,
            "parcels": counts, "parcels_unverified": unverified,
            "unverified": bool(unverified) or bool(g and not gp.get("verified")),
            "as_of": pr["as_of"], "hover_line": hover,
            "progress_url": f"/api/v1/projects/{pr['project_id']}/progress",
        })
    return {"as_of": today.isoformat(), "projects": out}


def key_status() -> dict:
    """실시간 조회 키가 있는지만 ('있음'/'없음'). 값은 어디에도 내보내지 않는다."""
    from core.live.http import env_key
    has = {"vworld": bool(env_key("VWORLD_API_KEY")),
           "juso": bool(env_key("JUSO_CONFM_KEY") or env_key("JUSO_CONFM_KEY_ALT"))}
    notes = []
    if not has["juso"]:
        notes.append("도로명주소 키 없음: 주소 검색은 브이월드 검색으로 대체합니다")
    if not has["vworld"]:
        notes.append("브이월드 키 없음: 토지 정보는 미리 받아 둔 시연 주소만 보여 줍니다")
    return {"keys": {k: "있음" if v else "없음" for k, v in has.items()}, "key_notes": notes}


# ---- 지도 클릭 필지 조회 (P15) ----
LIVE_OFF_NOTE = "실시간 조회를 쓰지 않는 설정이라 필지를 조회하지 못했습니다"
CLICK_LAT = (37.40, 37.60)          # 강남구 주변 (화면 URL 범위와 같음). 밖이면 API 400
CLICK_LON = (126.90, 127.25)
LAND_KEYS = ("status", "jimok", "area_m2", "land_use_zone", "land_use_zone2", "zones", "official_price",
             "use_situation", "missing", "source", "fetched_at", "from_cache", "cache", "found", "note")


def in_click_range(lat: float, lon: float) -> bool:
    return CLICK_LAT[0] <= lat <= CLICK_LAT[1] and CLICK_LON[0] <= lon <= CLICK_LON[1]


def _allowed_bjd(con) -> set:
    return {r["bjd_code"] for r in con.execute("SELECT bjd_code FROM bjd_codes")}


def _assemble(con, parcel: dict, live, today, point: tuple | None) -> dict:
    m = meta(con)
    base = {"status": parcel["status"], "message": parcel.get("note"), "pnu": parcel.get("pnu"),
            "jibun_address": parcel.get("address"), "boundary": parcel.get("boundary"),
            "centroid": parcel.get("centroid"), "as_of": m.get("as_of"), "source": parcel.get("source"),
            "land": None, "land_use_documented": None, "building": None, "building_note": None, "layer_counts": None,
            "dong_projects": [], "included_projects": [], "nearby_projects": [], "nearby_note": None,
            "ref_zones": [], "disclaimer": DISCLAIMER}
    if parcel["status"] != "ok":
        return base
    r = lookup_pnu(con, parcel["pnu"], today=today, live=live, location=parcel.get("centroid"))
    if r["status"] != "ok":
        return base | {"status": "outside" if r["status"] == "out_of_scope" else r["status"], "message": r["message"]}
    L = r["layers"]
    pc = L["parcel"]
    land = pc["land"] or {}
    n = r["normalized"]
    lat, lon = point if point else ((parcel["centroid"] or {}).get("lat"), (parcel["centroid"] or {}).get("lon"))
    return base | {
        "jibun_address": n["jibun_address"] or parcel.get("address"),
        "dong_name": n["dong_name"], "addr_id": n["addr_id"], "coord_source": n["coord_source"],
        "land": {k: land.get(k) for k in LAND_KEYS},
        "land_use_documented": pc["land_use_documented"],
        "building": pc["building"], "building_note": pc["building_note"],
        "layer_counts": {"city": len(L["city"]), "gu": len(L["gu"]["items"]), "dong": len(L["dong"]["items"]),
                         "parcel": len(pc["items"])},
        "dong_projects": [{"project_id": p["project_id"], "name": p["name"]} for p in L["dong"]["projects"]],
        "included_projects": pc["included_projects"], "nearby_projects": pc["nearby_projects"],
        "nearby_note": pc["nearby_note"],
        "ref_zones": refzones.zones_at(lat, lon) if lat is not None and lon is not None else [],
    }


def _offline(con) -> dict:
    return _assemble(con, {"status": "unavailable", "note": LIVE_OFF_NOTE}, None, None, None)


def parcel_at(con, lat: float, lon: float, live, today=None) -> dict:
    """GET /api/v1/map/parcel-at: 누른 점 → 필지 → 기존 조회. 주소 검색(도로명주소·브이월드 검색)은 거치지 않는다."""
    if live is None:
        return _offline(con)
    parcel = live.parcel_at(lat, lon, allowed_bjd=_allowed_bjd(con))
    return _assemble(con, parcel, live, today, (lat, lon))


def parcel_by_pnu(con, pnu: str, live, today=None) -> dict:
    """GET /api/v1/map/parcel?pnu= : URL sel=parcel:{pnu} 복원용 (같은 조립)."""
    if live is None:
        return _offline(con)
    parcel = live.parcel_by_pnu(pnu, allowed_bjd=_allowed_bjd(con))
    return _assemble(con, parcel, live, today, None)
