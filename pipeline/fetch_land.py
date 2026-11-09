"""브이월드 토지 정보 빌드 캐시 (feedback2.md §3-3, 네트워크 사용, 빌드 때만).

대상: 범위 안 시연 주소, 사업 대표 필지(추출 JSON의 projects), 대청마을 지도 대조 후보(seed/daecheong_map_reading.csv).
- core/live/vworld.get_land()와 같은 코드로 받아 seed/land_cache.json(커밋함)에 쓴다 → 시연 주소는 네트워크 없이도 동작.
- 좌표(location): 브이월드 지오코더 결과는 저장할 수 없어(docs/map/PLAN.md 데이터 조건) seed/parcels.geojson의
  필지 경계 중심점(EPSG:5186 representative_point, pipeline.fetch_parcels)을 쓴다 (P13). 지오코더는 부르지 않는다.
- 사업 중심 좌표: 대표 지번 필지의 경계 중심점을 seed/project_coords.csv에 쓴다. 필지 경계가 없으면
  build/project_anchors_osm.csv(OSM 근사, geocode.py)를 '근사'로 표시해 쓴다.
- 원 응답은 build/vworld_raw/에만 남긴다 (커밋 안 함). 키 값은 출력·저장하지 않는다.

사용: python -m pipeline.fetch_land                  # 토지 3종을 다시 받고 좌표는 필지 중심점
     python -m pipeline.fetch_land --relocate-only  # 네트워크 없이 seed/land_cache.json의 좌표만 필지 중심점으로 바꿈
"""
import argparse
import csv
import json
import math

from core.live import vworld
from core.live.http import env_key, get_json
from pipeline.common import BUILD, DOC_ORDER, EXTRACTIONS, SEED, fail, log, setup_stdout

RAW = BUILD / "vworld_raw"
LOC_SOURCE = "vworld-2d:LP_PA_CBND_BUBUN representative_point"


def load_csv(path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parcel_points() -> dict[str, dict]:
    """seed/parcels.geojson → {pnu: {lat, lon, source}} (필지 경계 중심점)."""
    p = SEED / "parcels.geojson"
    if not p.exists():
        fail("seed/parcels.geojson이 없습니다 (python -m pipeline.fetch_parcels 먼저)")
    fc = json.loads(p.read_text(encoding="utf-8"))
    return {f["properties"]["pnu"]: {"lat": f["properties"]["centroid_lat"], "lon": f["properties"]["centroid_lon"],
                                     "source": LOC_SOURCE} for f in fc["features"]}


def set_location(land: dict, loc: dict | None) -> dict:
    """지오코더 없이 받은 land 블록에 필지 중심점을 넣고 missing·status를 다시 계산한다 (vworld.build_land와 같은 규칙)."""
    land["location"] = dict(loc) if loc else None
    missing = [m for m in land["missing"] if m != "좌표"] + ([] if loc else ["좌표"])
    land["missing"] = missing
    land["status"] = "ok" if not missing else ("unavailable" if len(missing) == 4 else "partial")
    return land


def dist_m(a: dict | None, b: dict | None) -> float | None:
    if not a or not b:
        return None
    dy = (a["lat"] - b["lat"]) * 110540.0
    dx = (a["lon"] - b["lon"]) * 111320.0 * math.cos(math.radians(a["lat"]))
    return math.hypot(dx, dy)


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--relocate-only", action="store_true", help="네트워크 없이 좌표만 바꾼다 (토지 값은 그대로)")
    args = ap.parse_args()
    key = "" if args.relocate_only else env_key(vworld.KEY_ENV)
    if not key and not args.relocate_only:
        fail("VWORLD_API_KEY가 없습니다 (.env 또는 환경변수). 좌표만 바꾸려면 --relocate-only")
    dongs = {r["bjd_code"]: r["dong_name"] for r in load_csv(SEED / "bjd_codes.csv")}
    targets: dict[str, str] = {}
    for r in load_csv(SEED / "demo_addresses.csv"):
        if r["in_scope"] == "1" and r["pnu"]:
            targets[r["pnu"]] = f"시연 {r['addr_id']}"
    projects = []
    for doc in DOC_ORDER:
        p = EXTRACTIONS / f"{doc}.json"
        if not p.exists():
            continue
        for prj in json.loads(p.read_text(encoding="utf-8"))["projects"]:
            rj = prj["representative_jibun"]
            code = next(c for c, n in dongs.items() if n == rj["dong"])
            pnu = f"{code}{'2' if rj.get('san') else '1'}{rj['main']:04d}{rj.get('sub', 0):04d}"
            projects.append((prj["project_key"], pnu, f"{rj['dong']} {rj['main']}"))
            targets.setdefault(pnu, f"사업 대표 {prj['project_key']}")
    for r in load_csv(SEED / "daecheong_map_reading.csv"):
        targets.setdefault(r["pnu"], "지도 대조 후보")

    RAW.mkdir(parents=True, exist_ok=True)
    points = parcel_points()
    old_path = SEED / "land_cache.json"
    old = {x["pnu"]: x for x in json.loads(old_path.read_text(encoding="utf-8"))} if old_path.exists() else {}

    def fetch(url, params):
        j = get_json(url, params, timeout=15, retries=1)
        tag = params.get("pnu") or params.get("address", "")
        name = f"{url.rsplit('/', 1)[-1]}_{tag}".replace(" ", "_")[:120]
        text = json.dumps(j, ensure_ascii=False)
        if key in text:
            fail("원 응답에 키가 들어 있어 저장하지 않습니다")
        (RAW / f"{name}.json").write_text(text, encoding="utf-8")
        return j

    lands = []
    if args.relocate_only:
        missing_t = sorted(set(targets) - set(old))
        if missing_t:
            fail(f"seed/land_cache.json에 없는 대상 {missing_t} — 전체 실행이 필요합니다")
    for pnu, why in sorted(targets.items()):
        if args.relocate_only:
            lands.append(set_location(json.loads(json.dumps(old[pnu])), points.get(pnu)))
            continue
        land = vworld.get_land(pnu, None, fetch=fetch, use_cache=False)        # 지오코더는 부르지 않는다
        land = set_location(land, points.get(pnu))
        lands.append(land)
        log(f"{pnu} {why:28s} {land['status']:8s} {land['jimok']} {land['area_m2']}㎡ {land['land_use_zone']} "
            f"| {land['use_situation']} | 공시지가 {(land['official_price'] or {}).get('won_per_m2')}"
            + (f" | 못 받음: {', '.join(land['missing'])}" if land["missing"] else ""))
    text = json.dumps(lands, ensure_ascii=False, indent=1)
    if key and key in text:
        fail("land_cache에 키가 들어 있어 저장하지 않습니다")
    (SEED / "land_cache.json").write_text(text + "\n", encoding="utf-8")

    log("좌표 변경: 이전 land_cache.location → 필지 경계 중심점")
    for land in lands:
        o = (old.get(land["pnu"]) or {}).get("location")
        d = dist_m(o, land["location"])
        log(f"  {land['pnu']} {targets[land['pnu']]:28s} {'-' if d is None else f'{d:6.1f}m'}  (이전 {(o or {}).get('source')})")
    keys = ("status", "jimok", "area_m2", "land_use_zone", "land_use_zone2", "use_situation", "road_side", "terrain",
            "official_price", "zones", "characteristics_year")
    changed = [(x["pnu"], k) for x in lands for k in keys if x["pnu"] in old and old[x["pnu"]].get(k) != x.get(k)]
    log(f"좌표 밖 토지 값 변화 {len(changed)}건" + (f": {changed[:20]}" if changed else ""))

    osm = {r["project_key"]: r for r in load_csv(BUILD / "project_anchors_osm.csv")}
    rows = []
    for pk, pnu, jibun in projects:
        loc = points.get(pnu)
        if loc:
            rows.append({"project_key": pk, "lat": f"{loc['lat']:.6f}", "lon": f"{loc['lon']:.6f}",
                         "coord_source": f"{LOC_SOURCE} (대표 지번 {jibun})",
                         "note": "고시의 대표 지번 필지 경계(연속지적도)의 중심점"})
        elif pk in osm and osm[pk].get("lat"):
            rows.append({"project_key": pk, "lat": osm[pk]["lat"], "lon": osm[pk]["lon"],
                         "coord_source": osm[pk]["note"], "note": "필지 경계가 없어 OSM 근사값을 씀"})
        else:
            rows.append({"project_key": pk, "lat": "", "lon": "", "coord_source": "", "note": "좌표 없음"})
    with open(SEED / "project_coords.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["project_key", "lat", "lon", "coord_source", "note"])
        w.writeheader()
        w.writerows(rows)
    ok = sum(x["status"] == "ok" for x in lands)
    log(f"seed/land_cache.json {len(lands)}필지 (ok {ok}) · seed/project_coords.csv 사업 {len(rows)}건")
    for r in rows:
        log(f"  사업 중심 {r['project_key']}: {r['lat']}, {r['lon']} ({r['coord_source']})")


if __name__ == "__main__":
    main()
