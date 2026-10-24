"""시연 주소 좌표 (OpenStreetMap Nominatim, 빌드 때만 네트워크 사용) (agents.md §8-8).

- 시도 순서: 도로명주소 → '건물명 강남구'. 첫 성공을 쓴다. (지번 질의는 오매칭이 있어 뺐다, §21)
- 행정구역 경계·동네(place) 중심점 결과는 필지 좌표가 아니므로 받지 않는다.
- 결과가 강남구 범위(위도 37.45~37.54, 경도 127.01~127.12)를 벗어나면 실패로 본다.
- build/geocode_cache.json 에 캐시 (재실행 시 네트워크 안 씀). 요청 사이 1.1초.
"""
import csv
import json
import math
import time

import httpx

from pipeline.common import BUILD, SEED, log, setup_stdout

URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "propedia-pretotype/0.1 (prototype demo)"}
CACHE = BUILD / "geocode_cache.json"
LAT_RANGE = (37.45, 37.54)
LON_RANGE = (127.01, 127.12)


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {}


def query(q: str, cache: dict) -> list:
    if q in cache:
        return cache[q]
    for attempt in range(2):
        try:
            r = httpx.get(URL, params={"q": q, "format": "jsonv2", "limit": 1, "countrycodes": "kr"},
                          headers=HEADERS, timeout=20)
            time.sleep(1.1)
            if r.status_code == 200:
                cache[q] = r.json()
                return cache[q]
            log(f"  Nominatim HTTP {r.status_code} ({q})")
        except httpx.HTTPError as e:
            log(f"  Nominatim 네트워크 오류 {type(e).__name__} ({q})")
            time.sleep(1.1)
    return []


def accept(res: list) -> tuple[float, float] | None:
    if not res:
        return None
    x = res[0]
    # 행정경계·동네(place) 중심점, 도로·버스정류장(highway)은 필지 좌표가 아니다
    if x.get("category") in ("boundary", "place", "highway") or x.get("type") == "administrative":
        return None
    lat, lon = float(x["lat"]), float(x["lon"])
    if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
        return None
    return lat, lon


def main() -> None:
    setup_stdout()
    p = SEED / "demo_addresses.csv"
    with open(p, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        rows = list(reader)
    cache = load_cache()
    failed = []
    for r in rows:
        if r["in_scope"] != "1" or not r["pnu"]:
            continue
        # 지번 질의는 쓰지 않는다: 한국 OSM 번지는 도로명 번호라 '대치동 316'이 '선릉로 316'으로 잘못 맞았다 [확인 2026-10-25]
        tries = [("road", r["road_address"]),
                 ("building", f"{r['building_name']} 강남구" if r["building_name"] else "")]
        got = None
        for kind, q in tries:
            if not q:
                continue
            ll = accept(query(q, cache))
            if ll:
                got = (kind, ll)
                break
        if got:
            kind, (lat, lon) = got
            r["lat"], r["lon"], r["coord_source"] = f"{lat:.7f}", f"{lon:.7f}", f"osm-nominatim:{kind}"
        else:
            r["lat"] = r["lon"] = r["coord_source"] = ""
            failed.append(r["addr_id"])
    BUILD.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    a1 = next(r for r in rows if r["addr_id"] == "A1")
    log("addr_id | lat | lon | 출처 | A1과 거리")
    for r in rows:
        if not r["pnu"]:
            continue
        d = ""
        if a1["lat"] and r["lat"]:
            d = f"{haversine_m(float(a1['lat']), float(a1['lon']), float(r['lat']), float(r['lon'])):.0f}m"
        log(f"{r['addr_id']} | {r['lat'] or '-'} | {r['lon'] or '-'} | {r['coord_source'] or '좌표 없음'} | {d}")
    if failed:
        log(f"※ 좌표를 못 얻은 주소: {', '.join(failed)} → HUMAN_TODO '지도에서 위경도 확인 필요'")


if __name__ == "__main__":
    main()
