"""Propedia 지도 레이어 (docs/map/PLAN.md P13-5). 네트워크 안 씀.

입력: seed/boundaries/{D1,D9,D10,D5}.geojson (도면 정합 경계, 있는 것만), seed/parcels.geojson (필지 경계),
     db/propedia.db (읽기 전용: 사업명·단계·기준일·포함 판정 필지·규제 효력 기간)
출력 public/data/layers/:
  propedia_projects.geojson     사업 구역 (D1·D9)
  propedia_impact.geojson       영향권: 사업 구역을 EPSG:5186에서 250m·500m 넓힌 면 (링 아님)
  propedia_parcels.geojson      포함 판정 필지 (project_parcels)
  propedia_regulations.geojson  규제 구역 (D10, D5는 경계를 채택했을 때만)
  manifest.json                 레이어별 원천·기준일·건수·라이선스. 실행 시각은 넣지 않는다 (멱등).
- P14 겹침 보기: 필지·규제 도형마다 within_impact {project_id, buffer_m} — 중심점이 들어가는 가장 작은 영향권
  (EPSG:5186, 같으면 project_id 작은 쪽, 밖이면 둘 다 null). MapLibre 식용으로 impact_buffer_m(같은 값)도 넣는다.
- 좌표 소수 6자리, sort_keys. 같은 입력이면 같은 바이트.
- 서울플랜+(UQ120) 도형은 여기서 쓰지 않는다.

사용: python -m pipeline.build_map_layers
"""
import json

from shapely.geometry import Point, shape

from core.db import connect_ro
from core.map import INCLUSION, INCLUSION_LABEL
from core.progress import progress
from pipeline.boundaries import read_boundary
from pipeline.common import PUBLIC, SEED, fail, log, setup_stdout, sha256
from pipeline.geo import geom_out, to_4326, to_5186, write_fc

OUT = PUBLIC / "data" / "layers"
PROJECT_DOCS = {"apgujeong-6-1-hanyang7": "D1", "ilwon-daecheong-north-moatown": "D9"}
REGULATION_DOCS = ["D10", "D5"]
BUFFERS = (250, 500)
IMPACT_NOTE = "표시 기준이며 영향의 크기를 뜻하지 않음"
SOURCE_MAP = "고시 도면 × 브이월드 연속지적도(LP_PA_CBND_BUBUN) 대조 — Propedia 판독, 사람 확인 전"
LICENSE_VWORLD = "브이월드 2D 데이터 (국토교통부), 공공누리 1유형 출처표시"


def within_impact(pt5186, zones: list) -> dict:
    """중심점(EPSG:5186)이 들어가는 가장 작은 영향권. zones = [(buffer_m, project_id, 면)]"""
    for m, pid, g in sorted(zones, key=lambda z: (z[0], z[1])):
        if g.contains(pt5186):
            return {"project_id": pid, "buffer_m": m}
    return {"project_id": None, "buffer_m": None}


def main() -> None:
    setup_stdout()
    con = connect_ro()
    as_of = con.execute("SELECT value FROM meta WHERE key='as_of'").fetchone()[0]

    # 사업 구역 + 영향권
    projects, impact, notes, zones = [], [], [], []
    for p in con.execute("SELECT * FROM projects ORDER BY id"):
        doc = PROJECT_DOCS.get(p["project_key"])
        b = read_boundary(doc) if doc else None
        if b is None:
            notes.append(f"{p['project_key']}: 경계 없음 (도면 정합 전)")
            continue
        g5186 = to_5186(shape(b["geometry"]))
        bp = b["properties"]
        prog = progress(con, p["id"])
        aliases = json.loads(p["aliases"] or "[]")
        props = {"id": f"project:{p['id']}", "kind": "project", "name": p["name"], "project_key": p["project_key"],
                 "short_name": aliases[0] if aliases else p["name"],
                 "stage_code": p["sub_stage_code"], "stage_label": prog["position_label"], "basis": "map_reading",
                 "verified": 0, "doc_ids": [doc], "source_page": bp["source_page"].replace(" p0", " p"),
                 "as_of": p["stage_as_of"], "area_m2_doc": p["area_m2"], "area_m2_geom": round(g5186.area, 1),
                 "align_score": bp["align_score"]}
        projects.append({"type": "Feature", "id": props["id"], "properties": props, "geometry": b["geometry"]})
        for m in BUFFERS:
            ring = g5186.buffer(m, quad_segs=16)
            zones.append((m, p["id"], ring))
            impact.append({"type": "Feature", "id": f"impact:{p['id']}:{m}", "properties": {
                "id": f"impact:{p['id']}:{m}", "kind": "impact", "project_id": p["id"], "name": p["name"],
                "buffer_m": m, "note": IMPACT_NOTE, "basis": "map_reading", "verified": 0, "doc_ids": [doc],
                "source_page": props["source_page"], "as_of": p["stage_as_of"],
                "area_m2_geom": round(ring.area, 1)}, "geometry": geom_out(to_4326(ring))})

    # 포함 판정 필지
    pfc = json.loads((SEED / "parcels.geojson").read_text(encoding="utf-8"))
    pgeo = {f["properties"]["pnu"]: f for f in pfc["features"]}
    parcels, missing = [], []
    for r in con.execute("""SELECT pp.pnu, pp.basis, pp.verified, pp.project_id, p.name, p.project_key, d.doc_id,
                                   pp.pdf_page FROM project_parcels pp JOIN projects p ON p.id = pp.project_id
                            LEFT JOIN documents d ON d.id = pp.source_doc_id ORDER BY pp.project_id, pp.pnu"""):
        f = pgeo.get(r["pnu"])
        if f is None:
            missing.append(r["pnu"])
            continue
        inc = "included" if r["verified"] else INCLUSION.get(r["basis"], "possible")
        fp = f["properties"]
        props = {"id": f"parcel:{r['project_id']}:{r['pnu']}", "kind": "parcel", "pnu": r["pnu"], "jibun": fp["jibun"],
                 "name": f"{(fp['addr'] or '').replace('서울특별시 강남구 ', '')}", "project_id": r["project_id"],
                 "project_name": r["name"], "inclusion": inc, "inclusion_label": INCLUSION_LABEL[inc],
                 "basis": r["basis"], "verified": r["verified"], "doc_ids": [r["doc_id"]] if r["doc_id"] else [],
                 "source_page": f"{r['doc_id']} p{r['pdf_page']}" if r["doc_id"] and r["pdf_page"] else None,
                 "as_of": fp["as_of"], "area_m2_geom": fp["area_m2"],
                 "centroid_lon": fp["centroid_lon"], "centroid_lat": fp["centroid_lat"]}
        wi = within_impact(to_5186(Point(fp["centroid_lon"], fp["centroid_lat"])), zones)
        props |= {"within_impact": wi, "impact_buffer_m": wi["buffer_m"]}
        parcels.append({"type": "Feature", "id": props["id"], "properties": props, "geometry": f["geometry"]})
    if missing:
        fail(f"seed/parcels.geojson에 없는 사업 필지 {missing} (pipeline.fetch_parcels 먼저)")

    # 규제 구역
    regs = []
    for doc in REGULATION_DOCS:
        b = read_boundary(doc)
        rule = con.execute("""SELECT a.item_key, a.title, a.effective_from, a.effective_to, d.gosi_no, d.published_at,
                                     d.short_title FROM applicability_rules a JOIN documents d ON d.id = a.document_id
                              WHERE d.doc_id = ? ORDER BY a.item_key LIMIT 1""", (doc,)).fetchone()
        if b is None:
            notes.append(f"{doc}: 경계 확인 전, 법정동({'압구정동' if doc == 'D5' else '대치동'}) 단위로만 표시")
            continue
        bp = b["properties"]
        g5186 = to_5186(shape(b["geometry"]))
        props = {"id": f"regulation:{doc}", "kind": "regulation", "name": rule["short_title"], "item_key": rule["item_key"],
                 "gosi_no": rule["gosi_no"], "effective_from": rule["effective_from"], "effective_to": rule["effective_to"],
                 "basis": "map_reading", "verified": 0, "doc_ids": [doc], "source_page": bp["source_page"].replace(" p0", " p"),
                 "as_of": rule["published_at"], "area_m2_doc": bp["area_m2_doc"], "area_m2_geom": round(g5186.area, 1),
                 "align_score": bp["align_score"]}
        wi = within_impact(g5186.centroid, zones)
        props |= {"within_impact": wi, "impact_buffer_m": wi["buffer_m"]}
        regs.append({"type": "Feature", "id": props["id"], "properties": props, "geometry": b["geometry"]})
    con.close()

    layers = {
        "propedia_projects": (projects, "사업 구역 (고시 도면 정합)", SOURCE_MAP),
        "propedia_impact": (impact, "영향권 250m·500m (" + IMPACT_NOTE + ")", "사업 구역 경계에서 EPSG:5186 버퍼"),
        "propedia_parcels": (parcels, "포함 판정 필지", "project_parcels + " + LICENSE_VWORLD),
        "propedia_regulations": (regs, "규제 구역 (고시 도면 정합)", SOURCE_MAP),
    }
    manifest = {"generated_as_of": as_of, "crs": "EPSG:4326", "coordinate_decimals": 6, "notes": notes, "layers": {}}
    total = 0
    for name, (feats, title, src) in layers.items():
        path = OUT / f"{name}.geojson"
        write_fc(path, feats, name=name, title=title)
        n = path.stat().st_size
        total += n
        dates = sorted({f["properties"]["as_of"] for f in feats if f["properties"].get("as_of")})
        manifest["layers"][name] = {
            "file": f"{name}.geojson", "title": title, "source": src, "count": len(feats),
            "as_of": dates[-1] if dates else None, "doc_ids": sorted({d for f in feats for d in f["properties"]["doc_ids"]}),
            "license": "Propedia 판독 경계 (원천 고시: 공공저작물) · 필지선 " + LICENSE_VWORLD,
            "verified": "사람 확인 전 (verified=0)"}
        log(f"public/data/layers/{path.name}: {len(feats)}건 {n:,} B sha256 {sha256(path)[:16]}")
    mp = OUT / "manifest.json"
    try:          # 다른 스크립트가 쓴 항목(ref_*: pipeline/import_reference.py)은 그대로 둔다
        old = json.loads(mp.read_text(encoding="utf-8")).get("layers") or {}
    except (OSError, ValueError):
        old = {}
    manifest["layers"].update({k: v for k, v in old.items() if not k.startswith("propedia_")})
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    log(f"manifest.json sha256 {sha256(mp)[:16]} · 메모 {notes}")
    log(f"레이어 합계 {total:,} B ({total / 1024 / 1024:.2f} MB, 목표 2MB 이하)")


if __name__ == "__main__":
    main()
