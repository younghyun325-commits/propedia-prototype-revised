"""브이월드 토지 정보 빌드 캐시 (feedback2.md §3-3, 네트워크 사용, 빌드 때만).

대상: 범위 안 시연 주소, 사업 대표 필지(추출 JSON의 projects), 대청마을 지도 대조 후보(seed/daecheong_map_reading.csv).
- core/live/vworld.get_land()와 같은 코드로 받아 seed/land_cache.json(커밋함)에 쓴다 → 시연 주소는 네트워크 없이도 동작.
- 사업 중심 좌표: 대표 지번을 지오코더로 받은 좌표를 seed/project_coords.csv에 쓴다. 못 받으면
  build/project_anchors_osm.csv(OSM 근사, geocode.py)를 '근사'로 표시해 쓴다.
- 원 응답은 build/vworld_raw/에만 남긴다 (커밋 안 함). 키 값은 출력·저장하지 않는다.

사용: python -m pipeline.fetch_land
"""
import csv
import json

from core.live import vworld
from core.live.http import env_key, get_json
from pipeline.common import BUILD, DOC_ORDER, EXTRACTIONS, SEED, fail, log, setup_stdout

RAW = BUILD / "vworld_raw"


def load_csv(path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def jibun_of(pnu: str, dongs: dict) -> str:
    main, sub, san = int(pnu[11:15]), int(pnu[15:19]), pnu[10] == "2"
    return f"서울특별시 강남구 {dongs[pnu[:10]]} " + ("산 " if san else "") + f"{main}" + (f"-{sub}" if sub else "")


def main() -> None:
    setup_stdout()
    key = env_key(vworld.KEY_ENV)
    if not key:
        fail("VWORLD_API_KEY가 없습니다 (.env 또는 환경변수)")
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
    for pnu, why in sorted(targets.items()):
        land = vworld.get_land(pnu, jibun_of(pnu, dongs), fetch=fetch, use_cache=False)
        lands.append(land)
        log(f"{pnu} {why:28s} {land['status']:8s} {land['jimok']} {land['area_m2']}㎡ {land['land_use_zone']} "
            f"| {land['use_situation']} | 공시지가 {(land['official_price'] or {}).get('won_per_m2')}"
            + (f" | 못 받음: {', '.join(land['missing'])}" if land["missing"] else ""))
    text = json.dumps(lands, ensure_ascii=False, indent=1)
    if key in text:
        fail("land_cache에 키가 들어 있어 저장하지 않습니다")
    (SEED / "land_cache.json").write_text(text + "\n", encoding="utf-8")

    by_pnu = {x["pnu"]: x for x in lands}
    osm = {r["project_key"]: r for r in load_csv(BUILD / "project_anchors_osm.csv")}
    rows = []
    for pk, pnu, jibun in projects:
        loc = (by_pnu.get(pnu) or {}).get("location")
        if loc:
            rows.append({"project_key": pk, "lat": f"{loc['lat']:.7f}", "lon": f"{loc['lon']:.7f}",
                         "coord_source": f"vworld-geocoder:parcel (대표 지번 {jibun})",
                         "note": "고시의 대표 지번을 브이월드 지오코더로 찾은 좌표"})
        elif pk in osm and osm[pk].get("lat"):
            rows.append({"project_key": pk, "lat": osm[pk]["lat"], "lon": osm[pk]["lon"],
                         "coord_source": osm[pk]["note"], "note": "브이월드 좌표를 못 받아 OSM 근사값을 씀"})
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
