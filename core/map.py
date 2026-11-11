"""지도 화면용 조회 (docs/map/PLAN.md P14). 표준 라이브러리만, DB는 읽기 전용, 네트워크 없음.

- map_manifest: data/server/layers/manifest.json + data/server/base/ 를 읽어 레이어 목록(아직 없는 레이어는 pending)
  (서버가 읽는 파일은 CDN이 서빙하는 폴더 밖에 둔다 — 이유는 core/paths.py)
- state_at (P19): '그날 기준' 판정 하나 — 문서 발행 여부, 사업 표시·단계·기한(progress(today=그날)), 규제 효력 상태,
  상단 칩. map_projects·map_notices·map_feature·timeline·feed가 모두 이 함수를 쓴다 (날짜 계산은 core/timeutil)
- map_notices: 지도에 영역이 없는 서울 전역·강남구 단위 고시 (상단 바 칩). 효력 판정은 lookup.load_items 그대로
- map_projects: 사업 목록. 단계·기한은 progress() 결과를 그대로 쓰고 새로 계산하지 않는다
- timeline / feed (P19): 시간축 계열(고시 발행·공람·효력·사업 단계·자료 기준일)과 고시 피드
- key_status: 실시간 조회 키가 있는지 '있음/없음'만 (값은 절대 내보내지 않음)
- parcel_at / parcel_by_pnu: 지도 클릭 필지 조회 (P15). 필지 찾기는 core/live(브이월드 2D 데이터), 나머지는
  lookup_pnu(기존 4개 층 조립)·refzones(공식 참고 구역 점 판정)를 그대로 쓴다. 결과는 저장하지 않는다.
건수는 여기·화면·테스트 어디에도 숫자로 적지 않고 manifest·GeoJSON·DB에서 읽는다.
"""
import json
from pathlib import Path

from core.catalog import DOC_KIND_LABELS
from core.db import loads, meta, source
from core import refzones
from core.lookup import DISCLAIMER, load_items, lookup_pnu
from core.progress import progress
from core.regulation_display import chip_label, display_basis, display_title
from core.market import nearby_for_project
from core.paths import base_dir as _base_dir, layers_dir as _layers_dir
from core.review import Overrides
from core.timeutil import EFFECTIVE_SHORT_LABELS, d_day, effective, parse_date

ROOT = Path(__file__).resolve().parents[1]
SGG_GANGNAM = "11680"

# 포함 판정 (pipeline/build_map_layers.py도 이 표를 쓴다: 한 곳에서만 정의)
INCLUSION = {"representative_only": "possible", "map_reading": "likely", "manual_review": "included",
             "jibun_table": "included"}
INCLUSION_LABEL = {"included": "포함", "possible": "포함될 수 있음", "likely": "포함된 것으로 보임 (확인 필요)"}
JUDGMENTS = ("included", "possible", "likely")

UNAVAILABLE = ("지도 레이어 목록 파일(data/server/layers/manifest.json)을 읽지 못했습니다. "
               "pipeline.build_map_layers 뒤 pipeline.sync_server_data를 실행해 주세요")
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

# 생활 인프라 (P18): pipeline/fetch_pois.py가 manifest.json에 쓴 항목. 패널 id → manifest 키·이름·표시 방법
INFRA = [
    {"id": "schools", "key": "schools", "name": "학교", "default_on": True},
    {"id": "stations", "key": "stations", "name": "지하철역", "default_on": True},
    {"id": "bus_stops", "key": "bus_stops", "name": "버스정류장", "default_on": False, "min_zoom": 15,
     "label_min_zoom": 17},
    {"id": "pois", "key": "pois", "name": "편의시설", "default_on": False},
]
INFRA_KEYS = ("file", "size_bytes", "excluded", "as_of_note", "dataset_id", "url", "categories", "routes_file", "lazy",
              "license_note")
PENDING: list[dict] = []

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
    fc = _read_json(_layers_dir() / f"{name}.geojson")
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
    man = _read_json(_layers_dir() / "manifest.json")
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

    ap = L.get("apartments")
    entry("apartments", "market", "아파트 단지", "fill", ap, status="ready" if ap else "pending",
          note=(ap or {}).get("note") or "pipeline.build_map_layers 실행 전", lazy=True, file=(ap or {}).get("file"),
          size_bytes=(ap or {}).get("size_bytes"), points_file=(ap or {}).get("points_file"),
          fill_min_zoom=(ap or {}).get("fill_min_zoom"), boundary_note=(ap or {}).get("boundary_note"))

    for spec in INFRA:
        src = L.get(spec["key"])
        extra = {k: src.get(k) for k in INFRA_KEYS if src and k in src}
        if spec["key"] == "bus_stops" and L.get("bus_routes"):
            r = L["bus_routes"]
            extra["routes"] = {"file": r.get("file"), "count": r.get("count"), "source": r.get("source"),
                               "license": r.get("license"), "as_of": r.get("as_of"), "dataset_id": r.get("dataset_id"),
                               "url": r.get("url"), "as_of_note": r.get("as_of_note")}
        entry(spec["id"], "infra", spec["name"], "symbol", src, status="ready" if src else "pending",
              note=(src or {}).get("note") or (None if src else "pipeline.fetch_pois 실행 전"),
              default_on=spec["default_on"], min_zoom=spec.get("min_zoom"), label_min_zoom=spec.get("label_min_zoom"),
              **extra)

    for p in PENDING:
        layers.append({"id": p["id"], "group": p["group"], "name": p["name"], "kind": p["kind"], "source": p["source"],
                       "license": p["license"], "as_of": None, "count": None, "status": "pending",
                       "note": f"{p['available_from']} 준비 중", "available_from": p["available_from"],
                       "unverified": False, "doc_ids": [], "source_pages": [], **({"badge": p["badge"]} if p.get("badge") else {})})

    for id_, name, fn in (("boundary-gangnam", "강남구 경계", "gangnam"), ("boundary-bjd", "법정동 경계", "bjd")):
        fc = _read_json(_base_dir() / f"{fn}.geojson")
        entry(id_, "base", name, "line",
              {"source": "브이월드 2D 데이터 (국토교통부)", "license": VWORLD_LICENSE,
               "count": len(fc["features"]) if fc else None}, status="ready" if fc else "pending")

    return {"generated_as_of": man.get("generated_as_of"), "db_as_of": m.get("as_of"), "build_at": m.get("build_at"),
            "patched_at": m.get("patched_at"), "crs": man.get("crs"), "groups": GROUPS, "layers": layers, "notes": man.get("notes") or [],
            "market": market_status(ap)}


def market_status(ap: dict | None) -> dict:
    """데이터 상태 탭: 실거래(기간·건수·수집일·M23), 아파트 단지(단지 수·M22·기본 정보 연결 수 / 단지 목록 수).
    market.db가 없으면 available=False (다른 기능은 그대로)."""
    from core.db import connect_market_ro, loads
    try:
        mcon = connect_market_ro()
    except FileNotFoundError:
        return {"available": False, "layer_count": (ap or {}).get("count")}
    try:
        mm = {r["key"]: r["value"] for r in mcon.execute("SELECT key, value FROM meta")}
        linked = mcon.execute("SELECT COUNT(*) FROM apt_complexes WHERE basis_info_status='linked'").fetchone()[0]
        return {"available": True, "trade_from": mm.get("trade_from"), "trade_to": mm.get("trade_to"),
                "trade_count": int(mm.get("raw_count") or 0), "cancelled_count": int(mm.get("raw_cancelled") or 0),
                "fetched_on": mm.get("fetched_on"), "m22": loads(mm.get("m22"), None), "m23": loads(mm.get("m23"), None),
                "basis_linked": linked, "list_total": int(mm["list_total"]) if mm.get("list_total") else None,
                "basis_check": mm.get("basis_info_check"), "layer_count": (ap or {}).get("count")}
    finally:
        mcon.close()


REGULATION_DOC_KINDS = ("designation", "restriction", "press")
NOT_PUBLISHED_NOTE = "기준일({as_of})에는 아직 발행되지 않은 사업입니다 (첫 근거 문서 발행일 {date})"
REG_PUBLISHED_NOTE = "기준일({as_of})은 이 고시의 발행일({date}) 전입니다. 효력 기간은 원문에 적힌 날짜입니다"


def _notices(con, items: list[dict], kinds: dict, published: dict, as_of) -> list[dict]:
    """상단 칩: 서울 전역·강남구 단위 고시(계획 문서 제외) 중 그날 발행돼 있고 효력 중인 것"""
    out = []
    for it in items:
        refs = it["scope_ref"]
        wide = (it["scope_type"] == "SIDO" and "11" in refs) or (it["scope_type"] == "SGG" and SGG_GANGNAM in refs)
        doc = (it["source"] or {}).get("doc_id")
        kind = kinds.get(doc)
        if not wide or it["tier"] != "applies" or kind in (None, "plan"):
            continue
        if it["effective_status"] in ("ended", "not_started") or not published.get(doc):
            continue
        out.append({"doc_id": doc, "item_key": it["item_key"], "short_title": it["source"]["short_title"],
                    "chip_label": chip_label(it["item_key"], it["source"]["short_title"]),
                    "title": it["title"], "display_title": display_title(it["item_key"], it["title"]), "doc_kind": kind, "kind_label": DOC_KIND_LABELS.get(kind, kind),
                    "effective_from": it["effective_from"], "effective_to": it["effective_to"],
                    "effective_label": it["effective_label"], "effective_status_label": it["effective_status_label"],
                    "target_note": it["target_note"], "source": it["source"]})
    out.sort(key=lambda x: (int(x["doc_id"][1:]) if x["doc_id"][1:].isdigit() else 999, x["item_key"]))
    return out


def state_at(con, as_of) -> dict:
    """'그날 기준'으로 보이는 것 (P19, 순수 함수에 가깝게: DB 읽기 전용 + 그날 날짜만 받는다).
    - documents: 발행일 ≤ as_of면 shown
    - projects: 첫 근거 문서(project_documents) 발행일 ≤ as_of면 shown. 단계·기한·상태는 progress(today=as_of) 그대로
    - regulations: 규제 고시 항목의 원문 효력 기간과 as_of 비교 (timeutil.effective) — 효력 중 / 효력 전 / 종료
    - notices: 상단 칩 (발행돼 있고 효력 중인 서울 전역·강남구 단위 고시)"""
    docs = {r["doc_id"]: r for r in con.execute("SELECT id, doc_id, doc_kind, published_at FROM documents")}
    published = {k: bool(d["published_at"]) and parse_date(d["published_at"]) <= as_of for k, d in docs.items()}
    documents = {k: {"doc_id": k, "published_at": d["published_at"], "shown": published[k]} for k, d in docs.items()}

    projects = {}
    for p in con.execute("SELECT id FROM projects ORDER BY id"):
        first = con.execute("""SELECT MIN(d.published_at) FROM project_documents pd JOIN documents d ON d.id = pd.document_id
                               WHERE pd.project_id=?""", (p["id"],)).fetchone()[0]
        shown = bool(first) and parse_date(first) <= as_of
        pr = progress(con, p["id"], today=as_of) if shown else None
        projects[p["id"]] = {"id": p["id"], "feature_id": f"project:{p['id']}", "shown": shown, "shown_from": first,
                             "progress": pr, "status_badges": project_status_badges(pr) if pr else []}

    items = load_items(con, Overrides(), as_of)
    kinds = {k: d["doc_kind"] for k, d in docs.items()}
    regulations = {}
    for it in items:
        doc = (it["source"] or {}).get("doc_id")
        if kinds.get(doc) not in REGULATION_DOC_KINDS or it["tier"] != "applies":
            continue
        e = effective(it["effective_from"], it["effective_to"], as_of)
        regulations[it["item_key"]] = {
            "item_key": it["item_key"], "doc_id": doc, "feature_id": f"regulation:{doc}",
            "effective_from": it["effective_from"], "effective_to": it["effective_to"],
            "status": e["effective_status"], "status_label": EFFECTIVE_SHORT_LABELS.get(e["effective_status"]),
            "effective_label": e["effective_label"], "published": published.get(doc, False),
            "scope_type": it["scope_type"], "scope_ref": list(it["scope_ref"] or [])}
    return {"as_of": as_of.isoformat(), "documents": documents, "projects": projects, "regulations": regulations,
            "notices": _notices(con, items, kinds, published, as_of), "items": items}


def map_notices(con, today) -> dict:
    """상단 칩 + 지도 규제 레이어의 그날 효력 상태 (P19: 효력 중이 아니면 흐리게)"""
    st = state_at(con, today)
    regs = {}
    for r in st["regulations"].values():          # 문서 하나에 항목이 여럿이면 첫 항목(item_key 순)
        regs.setdefault(r["feature_id"], r)
    # P20: 지도 도형이 없는 규제(D5 법정동 단위, D6~D8 서울 전역)는 화면이 범위(scope)로 법정동·구 경계를 강조한다
    geoms = {f["properties"]["id"] for f in _features("propedia_regulations")}
    return {"as_of": st["as_of"], "items": st["notices"],
            "regulations": [{**{k: r[k] for k in ("feature_id", "doc_id", "item_key", "status", "status_label",
                                                  "effective_from", "effective_to", "scope_type", "scope_ref")},
                             "has_geometry": r["feature_id"] in geoms}
                            for r in sorted(regs.values(), key=lambda r: r["item_key"])]}


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


STATUS_OPEN = "공람 중"
STATUS_CLOSED = "공람 마감"
STATUS_NO_APPROVAL = "승인 고시 미확인"


def project_status_badges(pr: dict) -> list[str]:
    """사업 목록·인스펙터 상태 배지 (P16). progress() 값을 문구로 옮기기만 한다:
    공람 기한 open → 공람 중, closed → 공람 마감 / 단계 메모(stage_note: 승인 고시 확인 문서 없음)가 있으면 승인 고시 미확인."""
    out = []
    dl = next((d for d in pr["deadlines"] if d["kind"] == "public_review"), None)
    if dl:
        out.append(STATUS_OPEN if dl["status"] == "open" else STATUS_CLOSED)
    if pr["stage_note"] and "승인" in pr["stage_note"]:
        out.append(STATUS_NO_APPROVAL)
    return out


def map_projects(con, today, st: dict | None = None) -> dict:
    """사업 목록 (P19: 그날 발행된 근거 문서가 없는 사업은 {id, shown: false, shown_from}만)"""
    st = st or state_at(con, today)
    geoms = {f["properties"]["id"]: f for f in _features("propedia_projects")}
    out = []
    for p in con.execute("SELECT id FROM projects ORDER BY id").fetchall():
        sp = st["projects"][p["id"]]
        if not sp["shown"]:
            out.append({"id": p["id"], "feature_id": sp["feature_id"], "shown": False, "shown_from": sp["shown_from"]})
            continue
        pr = sp["progress"]
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
        status_badges = sp["status_badges"]
        dl_part = None
        if deadline:
            dl_part = (f"{deadline['title']} 마감" if deadline["status"] == "closed"
                       else f"{deadline['title']} {deadline['d_day_label']}")
        hover = " · ".join(x for x in [short, f"{cur['seq']}/{len(stages)}단계", dl_part] if x)
        out.append({
            "id": pr["project_id"], "feature_id": f"project:{pr['project_id']}", "shown": True,
            "shown_from": sp["shown_from"], "name": pr["name"],
            "short_name": short, "aliases": aliases, "project_type": pr["project_type"],
            "project_type_label": pr["project_type_label"], "position_label": pr["position_label"],
            "stage_seq": cur["seq"], "stage_total": len(stages), "stage_title": cur["title"],
            "status_badge": status_badge, "status_badges": status_badges, "stage_note": pr["stage_note"],
            "deadline": deadline,
            "representative_jibun": pr["location_text"], "representative_pnu": rep["pnu"] if rep else None,
            "bbox": _bbox(g["geometry"]) if g else None, "has_boundary": g is not None,
            "parcels": counts, "parcels_unverified": unverified,
            "unverified": bool(unverified) or bool(g and not gp.get("verified")),
            "as_of": pr["as_of"], "hover_line": hover,
            "progress_url": f"/api/v1/projects/{pr['project_id']}/progress",
        })
    return {"as_of": st["as_of"], "projects": out}


# ---- 참고 WMS 프록시 요청 검사 (P16 0단계) ----
WMS_MARGIN_M = 2000                 # 강남구 경계 bbox + 2km 안의 타일만 받는다
WMS_FORMAT = "image/png"
WMS_OUTSIDE = "강남구 주변(경계 + 2km) 타일만 받습니다"
WMS_BAD_FORMAT = "그림 형식은 image/png만 받습니다"
_gangnam_bbox: list[float] | None = None


def gangnam_bbox() -> list[float] | None:
    """data/server/base/gangnam.geojson의 [서, 남, 동, 북] (처음 한 번 읽음)"""
    global _gangnam_bbox
    if _gangnam_bbox is None:
        fc = _read_json(_base_dir() / "gangnam.geojson") or {}
        boxes = [b for b in (_bbox(f["geometry"]) for f in fc.get("features") or []) if b]
        if boxes:
            _gangnam_bbox = [min(b[0] for b in boxes), min(b[1] for b in boxes),
                             max(b[2] for b in boxes), max(b[3] for b in boxes)]
    return _gangnam_bbox


def tile_lonlat_bbox(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """XYZ 타일 → 경위도 (서, 남, 동, 북)"""
    import math
    n = 2 ** z

    def lat(yy: int) -> float:
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))
    return (x / n * 360 - 180, lat(y + 1), (x + 1) / n * 360 - 180, lat(y))


def wms_request_error(layer: str, z: int, x: int, y: int, size: int | None = None,
                      fmt: str | None = None) -> str | None:
    """참고 WMS 프록시 요청 검사. 문제가 있으면 한국어 안내 (API 400), 없으면 None."""
    import math
    from core.live import vworld
    bad = vworld.wms_check(layer, z, x, y, size)
    if bad:
        return bad
    if fmt is not None and fmt != WMS_FORMAT:
        return WMS_BAD_FORMAT
    gb = gangnam_bbox()
    if gb is None:
        return WMS_OUTSIDE
    dlat = WMS_MARGIN_M / 111_320
    dlon = WMS_MARGIN_M / (111_320 * math.cos(math.radians((gb[1] + gb[3]) / 2)))
    w, s, e, n = tile_lonlat_bbox(z, x, y)
    if w < gb[0] - dlon or e > gb[2] + dlon or s < gb[1] - dlat or n > gb[3] + dlat:
        return WMS_OUTSIDE
    return None


def map_config() -> dict:
    """지도 화면 설정 (P20). 배경지도(브이월드 WMTS) **브라우저용 키**만 실행 중에 내려준다 — 빌드(public/map)에 키를 넣지 않기 위해.
    브라우저 키는 어차피 타일 주소에 실려 브라우저에 보이며, 서비스 URL 제한으로 보호한다.
    키는 VITE_VWORLD_KEY만 읽는다. 서버용 VWORLD_API_KEY로 대신하지 않는다 (없으면 null → 화면은 경계만)."""
    from core.live.http import env_key
    key = env_key("VITE_VWORLD_KEY") or None
    return {"basemap": {"key": key, "configured": bool(key)}}


def key_status() -> dict:
    """실시간 조회 키가 있는지만 ('있음'/'없음'). 값은 어디에도 내보내지 않는다.
    예외는 map_config() 하나: 브라우저용 배경지도 키(VITE_VWORLD_KEY)만 지도 화면에 내려간다."""
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
            "ref_zones": [], "project_banner": [], "evidence": [], "disclaimer": DISCLAIMER}
    if parcel["status"] != "ok":
        return base
    r = lookup_pnu(con, parcel["pnu"], today=today, live=live, location=parcel.get("centroid"))
    if r["status"] != "ok":
        return base | {"status": "outside" if r["status"] == "out_of_scope" else r["status"], "message": r["message"]}
    L = r["layers"]
    pc = L["parcel"]
    land = pc["land"] or {}
    n = r["normalized"]
    banner, evidence = _parcel_banner_evidence(con, pc["included_projects"], L)
    lat, lon = point if point else ((parcel.get("centroid") or {}).get("lat"), (parcel.get("centroid") or {}).get("lon"))
    if lat is None or lon is None:        # 경계 없이 조립한 경우 (P16 대체 경로): 빌드 캐시의 필지 중심점
        lat, lon = n.get("lat"), n.get("lon")
    return base | {
        "jibun_address": n["jibun_address"] or parcel.get("address"),
        "dong_name": n["dong_name"], "addr_id": n["addr_id"], "coord_source": n["coord_source"],
        "land": {k: land.get(k) for k in LAND_KEYS},
        "land_use_documented": pc["land_use_documented"],
        "building": pc["building"], "building_note": pc["building_note"],
        "layer_counts": {"city": len(L["city"]), "gu": len(L["gu"]["items"]), "dong": len(L["dong"]["items"]),
                         "parcel": len(pc["items"])},
        "layer_items": {k: [_item_brief(it) for it in v] for k, v in
                        (("city", L["city"]), ("gu", L["gu"]["items"]), ("dong", L["dong"]["items"]),
                         ("parcel", pc["items"]))},
        "dong_projects": [{"project_id": p["project_id"], "name": p["name"]} for p in L["dong"]["projects"]],
        "included_projects": pc["included_projects"], "nearby_projects": pc["nearby_projects"],
        "nearby_note": pc["nearby_note"],
        "ref_zones": refzones.zones_at(lat, lon) if lat is not None and lon is not None else [],
        "project_banner": banner, "evidence": evidence,
    }


def _parcel_banner_evidence(con, included: list, L: dict) -> tuple[list, list]:
    """필지 보기 맨 위 '사업 구역 필지' 줄 (P16)과 원문 모달용 근거 목록. lookup 결과에서 고르기만 한다."""
    ev = _Evidence(_doc_meta(con))
    aliases = {row["id"]: loads(row["aliases"], []) for row in con.execute("SELECT id, aliases FROM projects")}
    banner = []
    for p in included:
        short = (aliases.get(p["project_id"]) or [p["name"]])[0]
        banner.append({"project_id": p["project_id"], "short_name": short, "inclusion": p["inclusion"],
                       "inclusion_label": p["inclusion_label"], "verified": p["inclusion"] == "included",
                       "review_id": p["review_id"], "basis_label": p["basis_label"], "source": p["source"]})
        ev.add(p["source"], None, f"사업 필지 · {p['basis_label']}")
    for v in (L["city"], L["gu"]["items"], L["dong"]["items"], L["parcel"]["items"]):
        for it in v:
            ev.add(it["source"], it["evidence"], it["title"])
    return banner, ev.items


def _item_brief(it: dict) -> dict:
    """필지 보기의 '걸린 고시' 펼치기용 (lookup 항목에서 고르기만 함)"""
    out = {k: it.get(k) for k in ("item_key", "title", "summary", "scope_label", "effective_label",
                                  "effective_status_label", "evidence", "source")}
    out["display_title"] = display_title(it["item_key"], it.get("title"))
    return out


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


# ---- 인스펙터 (P16): GET /api/v1/map/feature/{kind}/{id} ----
# 사업 = progress(), 규제 = load_items(), 필지 = parcel_by_pnu()/_assemble() 결과를 고르고 묶기만 한다.
# 새로 계산하는 값은 '남은 단계 수 = 템플릿 단계 수 − 현재 단계 번호' 하나뿐이다.
FEATURE_KINDS = {"project": "사업", "regulation": "규제", "parcel": "필지", "apartment": "아파트 단지"}
ROLE_LABELS = {"stage_basis": "단계 근거 문서", "related": "관련 문서"}
BOUNDARY_LABEL = "구역 경계 (결정도와 연속지적도 대조, 사람 확인 전)"
BOUNDARY_LABEL_OK = "구역 경계 (결정도와 연속지적도 대조)"
PARCEL_BOUNDARY_NOTE = "필지 경계를 지금 불러오지 못해 미리 받아 둔 자료로 보여 줍니다"
NOT_FOUND = {"project": "사업 {id}을(를) 찾을 수 없습니다", "regulation": "규제 고시 {id}을(를) 찾을 수 없습니다",
             "parcel": "필지 {id}을(를) 찾을 수 없습니다 (PNU 19자리 또는 사업번호:PNU)"}


class FeatureNotFound(Exception):
    """없는 kind·id → API 404"""


def _doc_meta(con) -> dict:
    return {r["doc_id"]: r for r in con.execute(
        "SELECT id, doc_id, title, short_title, gosi_no, issuer, published_at, doc_kind FROM documents")}


class _Evidence:
    """화면의 모든 출처 줄을 (문서, 쪽, 근거 문장) 기준으로 한 번씩 모은 목록 — 원문 모달의 이전/다음."""

    def __init__(self, docs: dict):
        self.docs, self.items, self.seen = docs, [], set()

    def add(self, src: dict | None, evidence: str | None, label: str) -> None:
        if not src:
            return
        k = (src["doc_id"], src.get("pdf_page"), evidence or "")
        if k in self.seen:
            return
        self.seen.add(k)
        d = self.docs.get(src["doc_id"])
        page = src.get("pdf_page")
        self.items.append({
            "doc_id": src["doc_id"], "short_title": src["short_title"], "title": d["title"] if d else None,
            "gosi_no": d["gosi_no"] if d else None, "published_at": src.get("published_at"),
            "pdf_page": page, "page_label": src.get("page_label"), "evidence": evidence,
            "page_image": src.get("page_image"), "label": label,
            "docs_url": f"/docs.html?doc={src['doc_id']}" + (f"&page={page}" if page else ""),
        })


def _source_page(con, docs: dict, sp: str | None) -> dict | None:
    """'D9 p12' → SOURCE (쪽 이미지 포함)"""
    if not sp or " p" not in sp:
        return None
    doc, _, pg = sp.partition(" p")
    d = docs.get(doc)
    return source(con, d["id"], int(pg)) if d and pg.isdigit() else None


def _date_desc(rows: list[dict]) -> list[dict]:
    rows = sorted(rows, key=lambda r: r.get("label") or "")
    return sorted(rows, key=lambda r: r.get("date") or "", reverse=True)


def _boundary(con, docs: dict, geo: dict | None) -> dict | None:
    if not geo:
        return None
    gp = geo["properties"]
    label = BOUNDARY_LABEL_OK if gp.get("verified") else BOUNDARY_LABEL
    return {"bbox": _bbox(geo["geometry"]), "verified": bool(gp.get("verified")), "label": label,
            "area_m2_doc": gp.get("area_m2_doc"), "area_m2_geom": gp.get("area_m2_geom"),
            "source": _source_page(con, docs, gp.get("source_page"))}


def feature_project(con, pid: int, today) -> dict | None:
    from core.lookup import parcel_projects
    from core.progress import WHAT_HAPPENS_NOTE, template_status
    st = state_at(con, today)
    sp = st["projects"].get(pid)
    if sp is None:
        return None
    if not sp["shown"]:                 # 그날에는 근거 문서가 아직 없음 — 이름·안내만
        p = con.execute("SELECT name, aliases FROM projects WHERE id=?", (pid,)).fetchone()
        aliases = loads(p["aliases"], [])
        return {"kind": "project", "id": str(pid), "kind_label": FEATURE_KINDS["project"],
                "title": aliases[0] if aliases else p["name"], "subtitle": p["name"], "badges": [], "unverified": False,
                "shown": False, "shown_from": sp["shown_from"],
                "note": NOT_PUBLISHED_NOTE.format(as_of=today.isoformat(), date=sp["shown_from"]),
                "as_of": today.isoformat(), "data_as_of": None, "bbox": None, "sections": {}, "evidence": [],
                "disclaimer": DISCLAIMER}
    pr = sp["progress"]
    docs = _doc_meta(con)
    ev = _Evidence(docs)
    card = next(p for p in map_projects(con, today, st)["projects"] if p["id"] == pid)
    tpl = {t["sub_stage_code"]: t for t in con.execute(
        "SELECT * FROM stage_templates WHERE project_type=?", (pr["project_type"],))}
    stages = []
    for s in pr["stages"]:
        t = tpl[s["code"]]
        stages.append(s | {"what_happens": t["what_happens"],
                           "what_happens_note": None if t["what_happens"] else WHAT_HAPPENS_NOTE,
                           "owner_actions": t["owner_actions"], "template_status": template_status(t)})
    cur = next(s for s in stages if s["status"] == "current")

    # 근거 (화면 순서)
    sb = pr["stage_basis"]
    ev.add(sb["source"], sb["evidence"], "현재 단계 근거")
    for d in pr["deadlines"]:
        ev.add(d["source"], None, d["title"])
    for f in pr["facts"]:
        ev.add(f["source"], f["evidence"], f["label"])
    geo = next((f for f in _features("propedia_projects") if f["properties"]["id"] == f"project:{pid}"), None)
    boundary = _boundary(con, docs, geo)
    if boundary:
        ev.add(boundary["source"], None, boundary["label"])

    # 사업 필지: 필지마다 기존 parcel_projects()의 판정을 그대로
    pgeo = {f["properties"]["pnu"]: f for f in _features("propedia_parcels")
            if f["properties"].get("project_id") == pid}
    parcels = []
    for r in con.execute("SELECT pnu, verified FROM project_parcels WHERE project_id=? ORDER BY pnu", (pid,)):
        norm = {"pnu": r["pnu"], "lat": None, "lon": None, "coord_source": None}
        row = next((x for x in parcel_projects(con, norm, Overrides())[0] if x["project_id"] == pid), None)
        if row is None:
            continue
        g = pgeo.get(r["pnu"])
        parcels.append({"pnu": r["pnu"], "feature_id": f"parcel:{pid}:{r['pnu']}",
                        "name": (g or {}).get("properties", {}).get("name") or r["pnu"],
                        "inclusion": row["inclusion"], "inclusion_label": row["inclusion_label"],
                        "basis": row["basis"], "basis_label": row["basis_label"], "verified": bool(r["verified"]),
                        "review_id": row["review_id"], "source": row["source"],
                        "bbox": _bbox(g["geometry"]) if g else None})
        ev.add(row["source"], None, f"사업 필지 · {row['basis_label']}")
    order = {"included": 0, "possible": 1, "likely": 2}
    parcels.sort(key=lambda p: (order.get(p["inclusion"], 9), p["name"]))

    # 이력: 단계 근거(고시) + 묶인 문서 + 관련 고시, 날짜 내림차순
    hist = []
    for h in con.execute("SELECT * FROM project_stage_history WHERE project_id=?", (pid,)):
        t = tpl.get(h["sub_stage_code"])
        hist.append({"date": h["entered_at"], "kind": "stage",
                     "label": f"{t['title'] if t else h['sub_stage_code']} 단계 근거",
                     "gosi_no": None, "evidence": h["evidence"], "source": source(con, h["source_doc_id"], h["pdf_page"])})
    for d in pr["documents"]:
        if not st["documents"].get(d["doc_id"], {}).get("shown"):
            continue                    # 그날 아직 발행되지 않은 문서는 근거에 넣지 않는다 (P19)
        dm = docs.get(d["doc_id"])
        hist.append({"date": d["published_at"], "kind": "document",
                     "label": f"{d['short_title']} ({ROLE_LABELS.get(d['role'], d['role'])})",
                     "gosi_no": dm["gosi_no"] if dm else None, "evidence": None,
                     "source": source(con, dm["id"], None) if dm else None})
    for r in pr["related_history"]:
        hist.append({"date": r["date"], "kind": "related", "label": r["label"], "gosi_no": r["gosi_no"],
                     "evidence": None, "source": r["source"]})
    for h in hist:
        ev.add(h["source"], h["evidence"], h["label"])

    badges = [{"text": pr["project_type_label"], "tone": "brand"}]
    badges += [{"text": b, "tone": "info" if b == STATUS_OPEN else "warn"} for b in card["status_badges"]]
    return {
        "kind": "project", "id": str(pid), "kind_label": FEATURE_KINDS["project"],
        "title": card["short_name"], "subtitle": pr["name"], "badges": badges, "unverified": card["unverified"],
        "shown": True, "shown_from": sp["shown_from"], "note": None,
        "as_of": today.isoformat(), "data_as_of": pr["as_of"], "bbox": card["bbox"],
        "sections": {
            "progress": pr | {"stages": stages},
            "stepper": {"total": len(stages), "current_seq": cur["seq"], "remaining_stages": len(stages) - cur["seq"],
                        "position_label": pr["position_label"],
                        "next_title": pr["next"]["title"] if pr["next"] else None},
            "status_badges": card["status_badges"],
            "boundary": boundary, "parcels": parcels, "history": _date_desc(hist),
            "nearby_apartments": nearby_for_project(con, pid),
        },
        "evidence": ev.items, "disclaimer": DISCLAIMER,
    }


def feature_regulation(con, rid: str, today) -> dict | None:
    docs = _doc_meta(con)
    doc_id = rid.split("-")[0]
    d = docs.get(doc_id)
    if d is None or d["doc_kind"] not in REGULATION_DOC_KINDS:
        return None
    st = state_at(con, today)
    items = [it for it in st["items"]
             if it["source"] and it["source"]["doc_id"] == doc_id and (rid == doc_id or it["item_key"] == rid)]
    items.sort(key=lambda it: (it["tier"] != "applies", it["item_key"]))
    if not items:
        return None
    it = items[0]
    ev = _Evidence(docs)
    ev.add(it["source"], it["evidence"], "근거 문장")
    for m in it["more_evidence"]:
        ev.add(m["source"], m["evidence"], m["label"])
    geo = next((f for f in _features("propedia_regulations") if f["properties"]["id"] == f"regulation:{doc_id}"), None)
    boundary = _boundary(con, docs, geo)
    boundary_note = None
    if boundary:
        ev.add(boundary["source"], None, boundary["label"])
    elif it["scope_type"] == "BJD":
        boundary_note = D5_NOTE if doc_id == "D5" else f"경계 확인 전, 법정동({it['scope_label']}) 단위로만 표시"
    hist = [{"date": d["published_at"], "kind": "document", "label": f"{d['short_title']} 공고",
             "gosi_no": d["gosi_no"], "evidence": None, "source": source(con, d["id"], None)}]
    if it["effective_from"]:
        hist.append({"date": it["effective_from"], "kind": "effective", "label": "효력 시작 (원문 기재)",
                     "gosi_no": None, "evidence": it["evidence"], "source": it["source"]})
    if it["effective_to"]:
        hist.append({"date": it["effective_to"], "kind": "effective", "label": "효력 끝 (원문 기재)",
                     "gosi_no": None, "evidence": it["evidence"], "source": it["source"]})
    kind_label = DOC_KIND_LABELS.get(d["doc_kind"], d["doc_kind"])
    badges = [{"text": kind_label, "tone": "brand"}]
    if it["effective_status_label"]:
        badges.append({"text": it["effective_status_label"],
                       "tone": "info" if it["effective_status"] == "in_force" else "muted"})
    reg = st["regulations"].get(it["item_key"])
    published = st["documents"][doc_id]["shown"]
    return {
        "kind": "regulation", "id": rid, "kind_label": FEATURE_KINDS["regulation"],
        "title": chip_label(it["item_key"], d["short_title"]), "subtitle": display_title(it["item_key"], it["title"]),
        "badges": badges,
        "unverified": bool(boundary and not boundary["verified"]) or bool(boundary_note),
        "shown": True, "published": published,
        "note": None if published else REG_PUBLISHED_NOTE.format(as_of=today.isoformat(), date=d["published_at"]),
        "status": reg["status"] if reg else it["effective_status"],
        "status_label": reg["status_label"] if reg else None,
        "as_of": today.isoformat(), "data_as_of": d["published_at"],
        "bbox": boundary["bbox"] if boundary else None,
        "sections": {
            "regulation": {"doc_id": doc_id, "item_key": it["item_key"], "doc_kind": d["doc_kind"],
                           "doc_kind_label": kind_label, "gosi_no": d["gosi_no"], "issuer": d["issuer"],
                           "published_at": d["published_at"], "title": it["title"],
                           "display_title": display_title(it["item_key"], it["title"]),
                           "display_basis": display_basis(it["item_key"]), "summary": it["summary"],
                           "scope_label": it["scope_label"], "target_note": it["target_note"],
                           "effective_from": it["effective_from"], "effective_to": it["effective_to"],
                           "effective_label": it["effective_label"], "effective_status": it["effective_status"],
                           "effective_status_label": it["effective_status_label"],
                           "evidence": it["evidence"], "evidence_ok": it["evidence_ok"], "source": it["source"],
                           "more_evidence": it["more_evidence"]},
            "boundary": boundary, "boundary_note": boundary_note, "history": _date_desc(hist),
        },
        "evidence": ev.items, "disclaimer": DISCLAIMER,
    }


def feature_parcel(con, fid: str, live, today) -> dict | None:
    pnu = fid.split(":")[-1]
    if not (pnu.isdigit() and len(pnu) == 19):
        return None
    r = parcel_by_pnu(con, pnu, live, today) if live is not None else None
    boundary_note = None
    if r is None or r["status"] in ("unavailable", "timeout"):
        # 실시간 필지 조회가 없거나 실패: 같은 조립을 경계 없이 (빌드 캐시 land_cache·DB만)
        r = _assemble(con, {"status": "ok", "pnu": pnu, "address": None, "boundary": None, "centroid": None,
                            "source": None}, None, today, None)
        boundary_note = PARCEL_BOUNDARY_NOTE
    if r["status"] in ("not_found", "outside"):
        raise FeatureNotFound(r.get("message") or NOT_FOUND["parcel"].format(id=fid))
    banner = r["project_banner"]
    badges = [{"text": b["inclusion_label"], "tone": "brand" if b["verified"] else "warn"} for b in banner]
    return {
        "kind": "parcel", "id": fid, "kind_label": FEATURE_KINDS["parcel"],
        "title": r.get("jibun_address") or pnu, "subtitle": pnu, "badges": badges,
        "unverified": any(not b["verified"] for b in banner),
        "as_of": today.isoformat(), "data_as_of": r.get("as_of"),
        "bbox": _bbox(r["boundary"]) if r.get("boundary") else None,
        "sections": {"parcel": r | {"boundary_note": boundary_note}, "project_banner": banner},
        "evidence": r["evidence"], "disclaimer": DISCLAIMER,
    }


def map_feature(con, kind: str, fid: str, live=None, today=None) -> dict:
    from core.timeutil import today_kst
    today = today or today_kst()
    if kind == "project":
        out = feature_project(con, int(fid), today) if fid.isdigit() else None
    elif kind == "regulation":
        out = feature_regulation(con, fid, today)
    elif kind == "parcel":
        out = feature_parcel(con, fid, live, today)
    else:
        raise FeatureNotFound("인스펙터 대상 종류는 project·regulation·parcel만 있습니다")
    if out is None:
        raise FeatureNotFound(NOT_FOUND[kind].format(id=fid))
    return out


# ---- 타임라인·고시 피드 (P19) ----
LANES = {"publish": "고시 발행", "review": "공람", "effective": "효력", "stage": "사업 단계", "data_as_of": "자료 기준일"}
RECENT_DAYS = 30


def _first_page(con, document_id: int) -> int | None:
    r = con.execute("SELECT MIN(pdf_page) FROM pages WHERE document_id=? AND selected=1", (document_id,)).fetchone()
    return r[0] if r else None


def _doc_sel(con, doc_id: str, kind: str, doc_projects: dict) -> str | None:
    """피드·타임라인에서 누를 때 고를 지도 대상: 사업 문서 → 사업, 규제 고시 → 규제 인스펙터, 계획 문서 → 없음"""
    if doc_projects.get(doc_id):
        return f"project:{doc_projects[doc_id][0]}"
    return f"regulation:{doc_id}" if kind in REGULATION_DOC_KINDS else None


def _doc_projects(con) -> dict:
    out: dict = {}
    for r in con.execute("""SELECT d.doc_id, pd.project_id FROM project_documents pd JOIN documents d ON d.id = pd.document_id
                            ORDER BY pd.project_id"""):
        out.setdefault(r["doc_id"], []).append(r["project_id"])
    return out


def _in_range(start, end, frm, to) -> bool:
    s, e = parse_date(start), parse_date(end) if end else None
    if s is None:
        return False
    return s <= to and (e is None or e >= frm)


def _ym_date(v: str | None) -> str | None:
    """레이어 기준일 '202609'·'2026-11-11' → 시간축 위치 'YYYY-MM-DD' (월만 있으면 그 달 1일)"""
    if not v:
        return None
    v = str(v)
    if len(v) == 6 and v.isdigit():
        return f"{v[:4]}-{v[4:]}-01"
    return v[:10] if len(v) >= 10 else None


def timeline(con, frm, to) -> dict:
    """계열별 이벤트 (P19). 점: 고시 발행·사업 단계·자료 기준일 / 막대: 공람 기간·효력 기간 (기간에 걸치면 포함).
    효력 기간은 원문에 적힌 날짜만 (끝이 없으면 end=null)."""
    docs = {r["doc_id"]: r for r in con.execute("SELECT * FROM documents")}
    by_id = {r["id"]: r for r in docs.values()}
    dp = _doc_projects(con)
    lanes: dict = {k: [] for k in LANES}
    for k, d in sorted(docs.items(), key=lambda x: x[1]["published_at"] or ""):
        if not _in_range(d["published_at"], d["published_at"], frm, to):
            continue
        lanes["publish"].append({
            "id": f"publish:{k}", "date": d["published_at"], "doc_id": k, "title": d["short_title"],
            "doc_kind": d["doc_kind"], "kind_label": DOC_KIND_LABELS.get(d["doc_kind"], d["doc_kind"]),
            "sel": _doc_sel(con, k, d["doc_kind"], dp), "source": source(con, d["id"], _first_page(con, d["id"]))})
    for dl in con.execute("SELECT * FROM deadlines WHERE kind='public_review' ORDER BY starts_on"):
        if not _in_range(dl["starts_on"], dl["due_on"], frm, to):
            continue
        lanes["review"].append({
            "id": f"review:{dl['project_id']}", "start": dl["starts_on"], "end": dl["due_on"], "title": dl["title"],
            "project_id": dl["project_id"], "sel": f"project:{dl['project_id']}",
            "doc_id": by_id[dl["source_doc_id"]]["doc_id"] if dl["source_doc_id"] in by_id else None,
            "source": source(con, dl["source_doc_id"], dl["pdf_page"])})
    seen = set()
    for it in load_items(con, Overrides(), to):
        doc = (it["source"] or {}).get("doc_id")
        d = docs.get(doc)
        if not d or d["doc_kind"] not in REGULATION_DOC_KINDS or it["tier"] != "applies" or not it["effective_from"]:
            continue
        if not _in_range(it["effective_from"], it["effective_to"], frm, to) or it["item_key"] in seen:
            continue
        seen.add(it["item_key"])
        lanes["effective"].append({
            "id": f"effective:{it['item_key']}", "start": it["effective_from"], "end": it["effective_to"],
            "title": d["short_title"], "doc_id": doc, "item_key": it["item_key"],
            "sel": _doc_sel(con, doc, d["doc_kind"], dp), "source": it["source"]})
    lanes["effective"].sort(key=lambda e: (e["start"], e["item_key"]))
    tpl = {(t["project_type"], t["sub_stage_code"]): t["title"] for t in con.execute("SELECT * FROM stage_templates")}
    for h in con.execute("""SELECT h.*, p.project_type FROM project_stage_history h JOIN projects p ON p.id = h.project_id
                            ORDER BY h.entered_at"""):
        if not _in_range(h["entered_at"], h["entered_at"], frm, to):
            continue
        lanes["stage"].append({
            "id": f"stage:{h['project_id']}:{h['sub_stage_code']}", "date": h["entered_at"],
            "title": tpl.get((h["project_type"], h["sub_stage_code"]), h["sub_stage_code"]), "code": h["sub_stage_code"],
            "project_id": h["project_id"], "sel": f"project:{h['project_id']}",
            "source": source(con, h["source_doc_id"], h["pdf_page"])})
    man = _read_json(_layers_dir() / "manifest.json") or {}
    m = meta(con)
    pts = [("db:as_of", "DB 기준일 (가장 최근 문서)", m.get("as_of"), m.get("as_of")),
           ("db:build_at", "DB 빌드", (m.get("build_at") or "")[:10] or None, (m.get("build_at") or "")[:10] or None)]
    for lid, L in sorted((man.get("layers") or {}).items()):
        if isinstance(L, dict) and L.get("as_of"):
            pts.append((f"layer:{lid}", f"{L.get('title') or lid} 자료 기준", _ym_date(L["as_of"]), str(L["as_of"])))
    for pid, title, date, label in pts:
        if date and _in_range(date, date, frm, to):
            lanes["data_as_of"].append({"id": pid, "date": date, "title": title, "as_of_label": label})
    lanes["data_as_of"].sort(key=lambda e: (e["date"], e["id"]))
    return {"from": frm.isoformat(), "to": to.isoformat(), "lane_labels": LANES, "lanes": lanes}


def feed(con, as_of, limit: int = 50) -> dict:
    """고시 피드 (P19): 발행일 ≤ 기준일인 문서, 최신순. 기한은 그 문서가 근거인 공람 기한의 그날 D-day."""
    st = state_at(con, as_of)
    dp = _doc_projects(con)
    names = {pid: (sp["progress"]["aliases"][0] if sp["progress"] and sp["progress"]["aliases"] else
                   (sp["progress"] or {}).get("name")) for pid, sp in st["projects"].items()}
    regs: dict = {}
    for r in st["regulations"].values():
        regs.setdefault(r["doc_id"], r)
    rows = []
    for d in con.execute("SELECT * FROM documents"):
        if not st["documents"][d["doc_id"]]["shown"]:
            continue
        related = [{"kind": "project", "id": f"project:{pid}", "label": names.get(pid)} for pid in dp.get(d["doc_id"], [])]
        reg = regs.get(d["doc_id"])
        if reg:
            related.append({"kind": "regulation", "id": reg["feature_id"], "label": reg["status_label"],
                            "effective_label": reg["effective_label"], "status": reg["status"]})
        deadline = None
        dl = con.execute("SELECT * FROM deadlines WHERE source_doc_id=? ORDER BY due_on LIMIT 1", (d["id"],)).fetchone()
        if dl:
            n, label = d_day(parse_date(dl["due_on"]), as_of)
            deadline = {"title": dl["title"], "starts_on": dl["starts_on"], "due_on": dl["due_on"], "d_day": n,
                        "d_day_label": label, "status": "open" if n >= 0 else "closed"}
        age = (as_of - parse_date(d["published_at"])).days
        rows.append({"doc_id": d["doc_id"], "title": d["title"], "short_title": d["short_title"], "doc_kind": d["doc_kind"],
                     "kind_label": DOC_KIND_LABELS.get(d["doc_kind"], d["doc_kind"]), "gosi_no": d["gosi_no"],
                     "issuer": d["issuer"], "published_at": d["published_at"], "related": related, "deadline": deadline,
                     "sel": _doc_sel(con, d["doc_id"], d["doc_kind"], dp), "recent_30d": 0 <= age < RECENT_DAYS,
                     "source": source(con, d["id"], _first_page(con, d["id"]))})
    rows.sort(key=lambda r: (r["published_at"], int(r["doc_id"][1:]) if r["doc_id"][1:].isdigit() else 0), reverse=True)
    return {"as_of": st["as_of"], "total": len(rows), "items": rows[:max(1, limit)]}
