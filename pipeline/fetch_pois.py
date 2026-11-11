"""P18 생활 인프라 레이어 빌드 (docs/map/PLAN.md P18, 결정 D1~D6).

원천 4종 → public/data/layers/
  schools.geojson     학교 (전국초중등학교위치표준데이터 CSV, 주소가 서울특별시 강남구 + 운영상태 '운영')
  stations.geojson    지하철역 (서울시 역사마스터 CSV, 강남구 경계 + 500m). 괄호를 뺀 이름이 같고 서로 300m 안이면 한 점(D5)
  bus_stops.geojson   버스정류장 (서울시 정류장마스터 CSV, 강남구 경계 + 100m, ARS마다 한 점, 같은 이름도 합치지 않음)
  bus_routes.json     강남구 정류장을 지나는 노선 (노선마스터 + 노선 정류장마스터). 선(경로)은 만들지 않는다
  pois.geojson        편의시설 (상가(상권)정보 API sdsc2 storeListInDong 강남구 전체 → seed/poi_categories.yaml 업종만)
                      1MB를 넘으면 분류별 pois_{key}.geojson으로 나눈다

규칙
- 좌표는 원자료의 위도·경도(WGS84) 그대로, 소수 6자리. 지오코딩·좌표 변환 저장 없음 (거리·경계 판정만 EPSG:5186).
- 원자료에 없는 정보(배차·평점·영업 여부 등)는 만들지 않는다. 노선 기점·종점은 원자료에 없어 필드도 만들지 않는다(D3).
- within_impact {project_id, buffer_m}: pipeline.build_map_layers.within_impact (영향권 = propedia_impact.geojson).
- 키: .env DATA_GO_KR_SERVICE_KEY. 키 값·키가 든 URL은 출력·저장하지 않는다. 원 응답은 build/pois_raw/ (커밋 안 함).
- 멱등: 원 응답 캐시가 있으면 다시 받지 않는다(이어받기). --refresh면 다시 받는다. 실행 시각을 결과에 넣지 않는다.
- 리포트: build/pois_report.json (호출 수·시간·건수·제외 사유·노선 연결·정류장 300m 검증·역 합치기)

사용: python -m pipeline.fetch_pois [--refresh] [--offline]
"""
import argparse
import csv
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from shapely.geometry import Point, shape
from shapely.prepared import prep

from pipeline import sync_server_data
from pipeline.build_map_layers import within_impact
from pipeline.common import BUILD, DATA_RAW, PUBLIC, SEED, fail, log, setup_stdout, sha256
from pipeline.geo import to_5186, write_fc

INFRA = DATA_RAW / "12.생활인프라"
SCHOOL_CSV = INFRA / "학교" / "전국초중등학교위치표준데이터.csv"
STATION_CSV = INFRA / "지하철역" / "서울시 역사마스터 정보.csv"
BUS_DIR = INFRA / "버스정류장"
STOP_CSV = BUS_DIR / "서울시 정류장마스터 정보.csv"
ROUTE_CSV = BUS_DIR / "서울시 노선마스터 정보.csv"
ROUTE_STOP_CSV = BUS_DIR / "서울시 노선 정류장마스터 정보.csv"
CATEGORIES = SEED / "poi_categories.yaml"
GANGNAM = PUBLIC / "data" / "base" / "gangnam.geojson"
OUT = PUBLIC / "data" / "layers"
RAW = BUILD / "pois_raw"
REPORT = BUILD / "pois_report.json"

SDSC = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInDong"
SGG = "11680"
PAGE_ROWS = 1000                 # numOfRows 최대 (1001을 요청해도 1000건, 2026-11-11 확인)
SPLIT_BYTES = 1_000_000

STATION_BUFFER_M = 500
BUS_BUFFER_M = 100
STATION_MERGE_M = 300            # D5
STATION_CHECK_M = 300            # D2 검증 기준
SAME_NAME_M = 100                # 인스펙터 '같은 이름의 정류장 n곳'
BUS_EXCLUDE_TYPES = {"가상정류장": "정류장 유형 '가상정류장'", "선착장": "정류장 유형 '선착장'"}

DOWNLOADED = "2026-11-11"        # 파일 내려받은 날 (CSV에 기준일 열 없음, D6)
SCHOOL_AS_OF = "2026-10-01"      # 파일의 데이터기준일자
SEOUL_LICENSE = "공공누리 1유형 : 출처표시 (상업적 이용 및 변경 가능)"
SOURCES = {
    "schools": {"source": "전국초중등학교위치표준데이터 (한국교육시설안전원)", "dataset_id": "data.go.kr 15021148",
                "url": "https://www.data.go.kr/data/15021148/standard.do",
                "license": "이용허락범위 제한 없음",
                "license_note": "2026-11-11 사람이 데이터셋 페이지에서 확인 (영현)",
                "as_of": SCHOOL_AS_OF, "as_of_note": "파일의 데이터기준일자"},
    "stations": {"source": "서울시 역사마스터 정보 (서울특별시)", "dataset_id": "OA-21232",
                 "url": "https://data.seoul.go.kr/dataList/OA-21232/S/1/datasetView.do", "license": SEOUL_LICENSE,
                 "as_of": DOWNLOADED, "as_of_note": "파일 내 기준일 없음, 내려받은 날 기준 (데이터셋 페이지 갱신일 2026.11.02)"},
    "bus_stops": {"source": "서울시 정류장마스터 정보 (서울특별시)", "dataset_id": "OA-21231",
                  "url": "https://data.seoul.go.kr/dataList/OA-21231/S/1/datasetView.do", "license": SEOUL_LICENSE,
                  "as_of": DOWNLOADED, "as_of_note": "파일 내 기준일 없음, 내려받은 날 기준 (데이터셋 페이지 갱신일 2026.11.02)"},
    "bus_routes": {"source": "서울시 노선마스터 정보 (OA-21230) + 서울시 노선 정류장마스터 정보 (OA-21233) (서울특별시)",
                   "dataset_id": "OA-21230, OA-21233",
                   "url": "https://data.seoul.go.kr/dataList/OA-21233/S/1/datasetView.do", "license": SEOUL_LICENSE,
                   "as_of": DOWNLOADED, "as_of_note": "파일 내 기준일 없음, 내려받은 날 기준 (데이터셋 페이지 갱신일 2026.11.02)"},
    "pois": {"source": "소상공인시장진흥공단 상가(상권)정보 (sdsc2 storeListInDong, 강남구)", "dataset_id": "data.go.kr 15012005",
             "url": "https://www.data.go.kr/data/15012005/openapi.do", "license": "이용허락범위 제한 없음",
             "as_of": "202609", "as_of_note": "응답 헤더 stdrYm (기준 연월)"},
}
_PAREN = re.compile(r"\([^)]*\)")


# ---------- 공통 ----------
def read_csv(path: Path) -> list[dict]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        fail(f"{path.name}: 인코딩을 읽지 못했습니다 (UTF-8·CP949 아님)")
    return list(csv.DictReader(text.splitlines()))


def num(v) -> float | None:
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return f if f != 0 else None


def r6(v: float) -> float:
    return round(v, 6)


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(a))


def gangnam_inside():
    """강남구 경계에서 m만큼 넓힌 면 안인지 (EPSG:5186, 경계 위 포함). inside(lon, lat, m) -> bool"""
    g = json.loads(GANGNAM.read_text(encoding="utf-8"))
    geom = shape(g["features"][0]["geometry"] if "features" in g else g["geometry"])
    g5 = to_5186(geom)
    cache: dict[int, object] = {}

    def inside(lon: float, lat: float, m: int) -> bool:
        if m not in cache:
            cache[m] = prep(g5.buffer(m, quad_segs=16) if m else g5)
        return cache[m].covers(to_5186(Point(lon, lat)))
    return inside


def load_zones() -> list:
    """영향권 [(buffer_m, project_id, 면 5186)] — build_map_layers가 만든 propedia_impact.geojson"""
    p = OUT / "propedia_impact.geojson"
    if not p.exists():
        fail("public/data/layers/propedia_impact.geojson이 없습니다. pipeline.build_map_layers를 먼저 실행해 주세요")
    fc = json.loads(p.read_text(encoding="utf-8"))
    return [(f["properties"]["buffer_m"], f["properties"]["project_id"], prep(to_5186(shape(f["geometry"]))))
            for f in fc["features"]]


def impact_props(lon: float, lat: float, zones: list) -> dict:
    wi = within_impact(to_5186(Point(lon, lat)), zones)
    return {"within_impact": wi, "impact_buffer_m": wi["buffer_m"]}


def point(fid: str, props: dict, lon: float, lat: float) -> dict:
    return {"type": "Feature", "id": fid, "properties": {"id": fid, **props, "lon": r6(lon), "lat": r6(lat)},
            "geometry": {"type": "Point", "coordinates": [r6(lon), r6(lat)]}}


# ---------- 학교 ----------
def school_features(rows: list[dict], zones: list) -> tuple[list[dict], dict]:
    gn = [r for r in rows if "서울특별시 강남구" in (r.get("소재지도로명주소", "") + r.get("소재지지번주소", ""))]
    feats, excluded = [], Counter()
    for r in gn:
        if r.get("운영상태") != "운영":
            excluded[f"운영상태 '{r.get('운영상태')}'"] += 1
            continue
        lon, lat = num(r.get("경도")), num(r.get("위도"))
        if lon is None or lat is None:
            excluded["좌표 없음"] += 1
            continue
        feats.append(point(f"school:{r['학교ID']}", {
            "kind": "school", "name": r["학교명"], "level": r["학교급구분"],
            "address": r.get("소재지도로명주소") or r.get("소재지지번주소"), "as_of": r.get("데이터기준일자") or SCHOOL_AS_OF,
            **impact_props(lon, lat, zones)}, lon, lat))
    feats.sort(key=lambda f: f["id"])
    return feats, {"raw_gangnam": len(gn), "excluded": dict(excluded), "count": len(feats),
                   "levels": dict(Counter(f["properties"]["level"] for f in feats))}


# ---------- 지하철역 ----------
def base_name(name: str) -> str:
    return _PAREN.sub("", name).strip()


def merge_stations(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """D5: 괄호를 뺀 이름이 같고 서로 300m 안이면 한 역. 위치는 호선이 가장 많은 원자료 이름의 행(같으면 역사_ID 작은 행).
    반환: (역 목록 [{name, aliases, lines, lon, lat, ids}], 합친 목록, 300m 넘어 안 합친 같은 이름 목록)"""
    by_base = defaultdict(list)
    for r in rows:
        by_base[base_name(r["역사명"])].append(r)
    out, merged, apart = [], [], []
    for b, rs in sorted(by_base.items()):
        groups: list[list[dict]] = []
        for r in sorted(rs, key=lambda r: (r["역사명"], int(r["역사_ID"]) if r["역사_ID"].isdigit() else 0, r["역사_ID"])):
            lon, lat = float(r["경도"]), float(r["위도"])
            for g in groups:
                if all(haversine_m(lon, lat, float(x["경도"]), float(x["위도"])) <= STATION_MERGE_M for x in g):
                    g.append(r)
                    break
            else:
                groups.append([r])
        if len(groups) > 1:
            apart.append({"name": b, "groups": [sorted({x["역사명"] for x in g}) for g in groups]})
        for g in groups:
            lines_by_name = Counter(x["역사명"] for x in g)
            top = max(lines_by_name.values())
            anchor_name = min(n for n, c in lines_by_name.items() if c == top)
            anchor = min((x for x in g if x["역사명"] == anchor_name), key=lambda x: (len(x["역사_ID"]), x["역사_ID"]))
            names = sorted({x["역사명"] for x in g})
            st = {"name": b, "aliases": names, "lines": sorted({x["호선"] for x in g}),
                  "lon": float(anchor["경도"]), "lat": float(anchor["위도"]), "ids": sorted({x["역사_ID"] for x in g}),
                  "anchor_id": anchor["역사_ID"].strip()}
            if len(names) > 1:
                merged.append({"name": b, "aliases": names, "lines": st["lines"], "anchor": anchor_name,
                               "max_distance_m": round(max(haversine_m(float(a["경도"]), float(a["위도"]),
                                                                       float(c["경도"]), float(c["위도"])) for a in g for c in g))})
            out.append(st)
    return out, merged, apart


def station_features(rows: list[dict], inside, zones: list) -> tuple[list[dict], dict]:
    excluded = Counter()
    keep = []
    for r in rows:
        lon, lat = num(r.get("경도")), num(r.get("위도"))
        if lon is None or lat is None:
            excluded["좌표 없음"] += 1
        elif not inside(lon, lat, STATION_BUFFER_M):
            excluded["강남구 경계 + 500m 밖"] += 1
        else:
            keep.append(r)
    stations, merged, apart = merge_stations(keep)
    folded = len(keep) - len(stations)
    feats = []
    for s in stations:
        # id = 위치를 가져온 원자료 행의 역사_ID (URL sel 값이 영문·숫자만 받으므로 역 이름 대신 코드)
        feats.append(point(f"station:{s['anchor_id']}", {"kind": "station", "name": s["name"], "aliases": s["aliases"],
                                 "lines": s["lines"], "station_ids": s["ids"],
                                 "as_of": DOWNLOADED, **impact_props(s["lon"], s["lat"], zones)}, s["lon"], s["lat"]))
    feats.sort(key=lambda f: f["id"])
    rep = {"raw_rows": len(rows), "rows_in_buffer": len(keep), "count": len(feats),
           "excluded_outside": dict(excluded),
           "excluded": {"같은 역의 다른 호선·이름 행 합침": folded} if folded else {},
           "merged": merged, "same_name_not_merged": apart}
    return feats, rep


# ---------- 버스정류장·노선 ----------
def norm_id(v: str) -> str:
    """노선·정류장 ID 키: 앞뒤 공백만 정리 (모두 9자리 숫자 문자열 — 2026-11-11 확인). 숫자로 바꾸지 않는다"""
    return str(v).strip()


def bus_build(stops: list[dict], routes: list[dict], route_stops: list[dict], inside, zones: list,
              as_of: str = DOWNLOADED) -> tuple[list[dict], list[dict], dict]:
    excluded, outside = Counter(), Counter()
    cand = []
    for r in stops:
        lon, lat = num(r.get("경도")), num(r.get("위도"))
        if lon is None or lat is None:
            outside["좌표 없음 또는 0"] += 1
            continue
        if not inside(lon, lat, BUS_BUFFER_M):
            outside["강남구 경계 + 100m 밖"] += 1
            continue
        cand.append((r, lon, lat))
    raw_gangnam = len(cand)
    keep = []
    for r, lon, lat in cand:
        t = (r.get("정류장_유형") or "").strip()
        if t in BUS_EXCLUDE_TYPES:
            excluded[BUS_EXCLUDE_TYPES[t]] += 1
        else:
            keep.append((r, lon, lat))
    # ARS마다 한 점. 같은 ARS가 여러 행이면 정류장_ID가 작은 행 (강남구에서는 0건, 2026-11-11 확인)
    by_ars = defaultdict(list)
    for r, lon, lat in keep:
        by_ars[r["정류장_번호"].strip()].append((r, lon, lat))
    dup = {a: sorted(norm_id(x[0]["정류장_ID"]) for x in v) for a, v in by_ars.items() if len(v) > 1}
    if dup:
        excluded["같은 ARS 번호의 다른 행 (정류장_ID가 작은 행을 남김)"] += sum(len(v) - 1 for v in dup.values())
    chosen = {a: min(v, key=lambda x: norm_id(x[0]["정류장_ID"])) for a, v in by_ars.items()}

    # 노선 연결 (D3): 서울 정류장 마스터에 없는 정류장 행은 버린다
    master_ids = {norm_id(r["정류장_ID"]) for r in stops}
    route_info = {norm_id(r["노선_ID"]): r for r in routes}
    rs_total = len(route_stops)
    rs_dropped_stop = sum(1 for r in route_stops if norm_id(r["정류장_ID"]) not in master_ids)
    rs_dropped_route = sum(1 for r in route_stops if norm_id(r["정류장_ID"]) in master_ids
                           and norm_id(r["노선_ID"]) not in route_info)
    stop_to_ars = {norm_id(x[0]["정류장_ID"]): a for a, x in chosen.items()}
    routes_of = defaultdict(set)
    seq_of = defaultdict(list)
    for r in route_stops:
        sid, rid = norm_id(r["정류장_ID"]), norm_id(r["노선_ID"])
        if sid not in master_ids or rid not in route_info or sid not in stop_to_ars:
            continue
        routes_of[sid].add(rid)
        seq_of[rid].append((int(float(r["정류장_순서"])), stop_to_ars[sid]))

    rtype = {rid: (route_info[rid].get("노선_유형") or "").strip() for rid in route_info}
    # 같은 이름 정류장 (100m 안)
    by_name = defaultdict(list)
    for a, (r, lon, lat) in chosen.items():
        by_name[r["정류장_명칭"].strip()].append((a, lon, lat))
    feats = []
    for a, (r, lon, lat) in sorted(chosen.items()):
        sid = norm_id(r["정류장_ID"])
        rids = sorted(routes_of.get(sid, ()))
        name = r["정류장_명칭"].strip()
        same = sorted(o for o, olon, olat in by_name[name] if o != a and haversine_m(lon, lat, olon, olat) <= SAME_NAME_M)
        stype = (r.get("정류장_유형") or "").strip() or None
        feats.append(point(f"bus:{a}", {
            "kind": "bus_stop", "ars_no": a, "stop_id": sid, "name": name, "stop_type": stype,
            "central_lane": stype == "중앙차로", "route_ids": rids, "route_count": len(rids),
            "route_types": dict(sorted(Counter(rtype[x] for x in rids).items())),
            "same_name_nearby": [f"bus:{o}" for o in same], "as_of": as_of, **impact_props(lon, lat, zones)}, lon, lat))
    bus_routes = []
    for rid in sorted(seq_of):
        info = route_info[rid]
        bus_routes.append({"route_id": rid, "route_no": info["노선_명칭"], "route_type": rtype[rid],
                           "gangnam_stop_ids": [ars for _, ars in sorted(seq_of[rid])], "as_of": as_of})
    linked = sum(1 for f in feats if f["properties"]["route_count"] > 0)
    rep = {"raw_rows": len(stops), "raw_gangnam": raw_gangnam, "excluded_outside": dict(outside),
           "excluded": dict(excluded), "duplicate_ars": dup, "count": len(feats),
           "stop_types": dict(Counter(f["properties"]["stop_type"] or "" for f in feats)),
           "names": len({f["properties"]["name"] for f in feats}),
           "names_with_multiple_stops": sum(1 for v in Counter(f["properties"]["name"] for f in feats).values() if v > 1),
           "route_stop_rows": rs_total,
           "route_stop_rows_dropped": {"정류장_ID가 서울 정류장 마스터에 없음 (경기·인천 등)": rs_dropped_stop,
                                       "노선_ID가 노선 마스터에 없음": rs_dropped_route},
           "link_rate_all": {"num": rs_total - rs_dropped_stop, "den": rs_total},
           "link_rate_gangnam": {"num": linked, "den": len(feats)},
           "no_route_stops": [{"ars_no": f["properties"]["ars_no"], "name": f["properties"]["name"]}
                              for f in feats if not f["properties"]["route_count"]],
           "routes": len(bus_routes), "route_types": dict(Counter(r["route_type"] for r in bus_routes)),
           "same_route_repeat_rows": sum(len(v) - len({s for _, s in v}) for v in seq_of.values())}
    return feats, bus_routes, rep


def station_stop_match(stop_name: str, station: str) -> bool:
    """정류장 이름이 '{역}역'으로 시작하고 바로 뒤가 끝·공백·'.'·'·'·'('·숫자일 때만 그 역의 정류장으로 본다
    (예: '강남역', '강남역 10번출구', '강남역.강남역사거리'). 부분 문자열 일치는 쓰지 않는다 (P19-0)."""
    return re.match(rf"{re.escape(station)}역(?=$|[\s.·(]|\d)", stop_name) is not None


def station_check(bus_feats: list[dict], station_feats: list[dict]) -> list[dict]:
    """D2 좌표 검증: 이름이 '{역 이름}역'으로 시작하는 강남구 정류장 ↔ 그 역 좌표 거리 (긴 역 이름 먼저)."""
    names = []
    for s in station_feats:
        for n in {s["properties"]["name"], *map(base_name, s["properties"]["aliases"])}:
            names.append((n, s))
    names.sort(key=lambda x: (-len(x[0]), x[0]))
    rows = []
    for f in bus_feats:
        p = f["properties"]
        for n, s in names:
            if station_stop_match(p["name"], n):
                d = haversine_m(p["lon"], p["lat"], s["properties"]["lon"], s["properties"]["lat"])
                rows.append({"ars_no": p["ars_no"], "stop_name": p["name"], "station": s["properties"]["name"],
                             "distance_m": round(d), "within_300m": d <= STATION_CHECK_M})
                break
    return sorted(rows, key=lambda r: (r["station"], r["distance_m"], r["ars_no"]))


# ---------- 편의시설 ----------
def load_categories(path: Path = CATEGORIES) -> tuple[dict, dict]:
    """(소분류 코드 → {category, label, sub, name}, 분류 key → 분류 정보)"""
    y = yaml.safe_load(path.read_text(encoding="utf-8"))
    if y.get("status") != "confirmed":
        fail("seed/poi_categories.yaml이 확정(status: confirmed) 전입니다")
    codes, cats = {}, {}
    for c in y["categories"]:
        cats[c["key"]] = {"key": c["key"], "label": c["label"], "icon": c["icon"], "note": c.get("note"),
                          "sub_categories": c.get("sub_categories") or [],
                          "sub_keys": c.get("sub_keys") or {},
                          "codes": {cd["code"]: cd["name"] for cd in c["codes"]}}   # 업종 소분류 이름은 manifest에서
        for cd in c["codes"]:
            codes[cd["code"]] = {"category": c["key"], "label": c["label"], "sub": cd.get("sub"), "name": cd["name"]}
    return codes, cats


def store_items(page: dict) -> list[dict]:
    return ((page or {}).get("body") or {}).get("items") or []


def poi_features(items: list[dict], codes: dict, zones: list, as_of: str) -> tuple[list[dict], dict]:
    excluded = Counter()
    feats, seen = [], set()
    for it in items:
        bid = str(it.get("bizesId") or "").strip()
        if bid in seen:
            excluded["같은 상가업소번호 중복 행"] += 1
            continue
        seen.add(bid)
        c = codes.get(it.get("indsSclsCd"))
        if c is None:
            excluded["분류표에 없는 업종"] += 1
            continue
        if str(it.get("signguCd")) != SGG:
            excluded["강남구 밖 (시군구 코드)"] += 1
            continue
        lon, lat = num(it.get("lon")), num(it.get("lat"))
        if lon is None or lat is None:
            excluded["좌표 없음"] += 1
            continue
        name = (it.get("bizesNm") or "").strip()
        if (it.get("brchNm") or "").strip():
            name = f"{name} {it['brchNm'].strip()}"
        props = {"kind": "poi", "name": name, "category": c["category"], "category_code": it["indsSclsCd"],
                 "address": (it.get("rdnmAdr") or it.get("lnoAdr") or "").strip() or None,
                 "as_of": as_of, **impact_props(lon, lat, zones)}
        if c["sub"]:
            props["sub_category"] = c["sub"]
        feats.append(point(f"poi:{bid}", props, lon, lat))
    feats.sort(key=lambda f: f["id"])
    by = Counter(f["properties"]["category"] for f in feats)
    sub = Counter((f["properties"]["category"], f["properties"].get("sub_category")) for f in feats
                  if f["properties"].get("sub_category"))
    return feats, {"raw": len(items), "excluded": dict(excluded), "count": len(feats), "by_category": dict(by),
                   "by_sub_category": {f"{k}/{s}": n for (k, s), n in sorted(sub.items())}}


def fetch_store_pages(refresh: bool, offline: bool) -> tuple[list[dict], dict]:
    """강남구 상가 전체 쪽. 캐시(build/pois_raw/p###.json)가 있으면 그대로 쓴다 (이어받기)."""
    stats = {"calls": 0, "seconds": 0.0, "pages": 0, "cached": 0}
    RAW.mkdir(parents=True, exist_ok=True)
    key = None

    def page(n: int) -> dict:
        nonlocal key
        p = RAW / f"p{n:03d}.json"
        if p.exists() and not refresh:
            stats["cached"] += 1
            return json.loads(p.read_text(encoding="utf-8"))
        if offline:
            fail(f"build/pois_raw/{p.name}가 없습니다 (--offline)")
        from pipeline.check_market_api import _key, call, has_key
        key = key or _key()
        t0 = time.time()
        st, body = call(SDSC, {"type": "json", "divId": "signguCd", "key": SGG, "pageNo": n, "numOfRows": PAGE_ROWS}, key)
        stats["calls"] += 1
        stats["seconds"] += time.time() - t0
        if has_key(body, key):
            fail("응답에 키 문자열이 있습니다 — 저장하지 않고 멈춥니다")
        try:
            js = json.loads(body)
        except ValueError:
            fail(f"{n}쪽 응답이 JSON이 아닙니다 (HTTP {st}). 내일 이어서 실행해 주세요", code=2)
        code = (js.get("header") or {}).get("resultCode")
        if st != 200 or code not in ("00", "03"):
            fail(f"{n}쪽 결과 코드 {code} (HTTP {st}). 받은 쪽은 build/pois_raw/에 남았으니 내일 이어서 실행해 주세요", code=2)
        js["header"].pop("columns", None)
        p.write_text(json.dumps(js, ensure_ascii=False, sort_keys=True), encoding="utf-8", newline="\n")
        return js

    first = page(1)
    total = int(first["body"]["totalCount"])
    pages = math.ceil(total / PAGE_ROWS)
    out = [first] + [page(n) for n in range(2, pages + 1)]
    stats["pages"] = pages
    stats["total_count"] = total
    stats["stdrYm"] = sorted({(p.get("header") or {}).get("stdrYm") for p in out} - {None})
    got = sum(len(store_items(p)) for p in out)
    if got != total:
        fail(f"상가 건수가 맞지 않습니다: 쪽 합계 {got} ≠ totalCount {total}. --refresh로 다시 받아 주세요")
    return out, stats


# ---------- 쓰기 ----------
def write_layer(name: str, feats: list[dict], title: str) -> tuple[Path, int]:
    path = OUT / f"{name}.geojson"
    write_fc(path, feats, name=name, title=title)
    return path, path.stat().st_size


def update_manifest(entries: dict, remove: set) -> Path:
    mp = OUT / "manifest.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    for k in remove:
        m["layers"].pop(k, None)
    m["layers"].update(entries)
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return mp


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="상가 원 응답을 다시 받는다")
    ap.add_argument("--offline", action="store_true", help="네트워크 없이 캐시만 쓴다")
    a = ap.parse_args()
    t0 = time.time()
    for p in (SCHOOL_CSV, STATION_CSV, STOP_CSV, ROUTE_CSV, ROUTE_STOP_CSV, CATEGORIES, GANGNAM):
        if not p.exists():
            fail(f"원천 파일이 없습니다: {p.relative_to(p.parents[2]) if len(p.parents) > 2 else p}")
    inside, zones = gangnam_inside(), load_zones()
    report: dict = {}
    entries: dict = {}

    schools, report["schools"] = school_features(read_csv(SCHOOL_CSV), zones)
    stations, report["stations"] = station_features(read_csv(STATION_CSV), inside, zones)
    bus, routes, report["bus"] = bus_build(read_csv(STOP_CSV), read_csv(ROUTE_CSV), read_csv(ROUTE_STOP_CSV), inside, zones)
    report["bus"]["station_check"] = station_check(bus, stations)
    pages, report["sdsc_fetch"] = fetch_store_pages(a.refresh, a.offline)
    codes, cats = load_categories()
    poi_as_of = report["sdsc_fetch"]["stdrYm"][-1] if report["sdsc_fetch"]["stdrYm"] else SOURCES["pois"]["as_of"]
    pois, report["pois"] = poi_features([it for p in pages for it in store_items(p)], codes, zones, poi_as_of)

    sizes = {}
    for name, feats, title in (("schools", schools, "학교 (초·중·고)"), ("stations", stations, "지하철역"),
                               ("bus_stops", bus, "버스정류장")):
        path, n = write_layer(name, feats, title)
        sizes[path.name] = n
        rep = report["bus" if name == "bus_stops" else name]
        entries[name] = {**SOURCES[name], "file": path.name, "title": title, "count": len(feats), "size_bytes": n,
                         "excluded": rep.get("excluded", {}), "lazy": name == "bus_stops"}
    entries["stations"]["note"] = "괄호를 뺀 역 이름이 같고 서로 300m 안이면 한 역으로 합침. 위치는 호선이 가장 많은 원자료 행의 좌표"
    entries["bus_stops"]["note"] = ("정류장 번호(ARS)마다 한 점, 같은 이름도 합치지 않음. 가상정류장·선착장 제외. "
                                    "노선 연결은 서울 정류장 마스터에 있는 정류장만 (경기·인천 정류장 행 제외)")
    entries["bus_stops"]["routes_file"] = "bus_routes.json"
    rp = OUT / "bus_routes.json"
    rp.write_text(json.dumps({"name": "bus_routes", "title": "강남구 정류장을 지나는 노선",
                              "note": "정류장 순번만 담음. 노선 경로 선은 실제 도로 경로가 아니므로 만들지 않음. 기점·종점은 원자료에 없음",
                              "routes": routes}, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                  encoding="utf-8", newline="\n")
    sizes[rp.name] = rp.stat().st_size
    entries["bus_routes"] = {**SOURCES["bus_routes"], "file": rp.name, "title": "버스 노선 (강남구 정류장 경유)",
                             "count": len(routes), "size_bytes": sizes[rp.name], "lazy": True, "panel": False,
                             "route_stop_rows_dropped": report["bus"]["route_stop_rows_dropped"]}

    # 편의시설: 1MB가 넘으면 분류별 파일
    for old in OUT.glob("pois*.geojson"):
        old.unlink()
    path, n = write_layer("pois", pois, "편의시설 (상가(상권)정보, 분류표 업종만)")
    files = {}
    if n > SPLIT_BYTES:
        path.unlink()
        for k in cats:
            pk, nk = write_layer(f"pois_{k}", [f for f in pois if f["properties"]["category"] == k], f"편의시설 — {cats[k]['label']}")
            files[k] = pk.name
            sizes[pk.name] = nk
    else:
        sizes[path.name] = n
    entries["pois"] = {**SOURCES["pois"], "title": "편의시설", "count": len(pois), "lazy": True,
                       "excluded": report["pois"]["excluded"], "size_bytes": sum(v for k, v in sizes.items() if k.startswith("pois")),
                       "categories": [{**cats[k], "count": report["pois"]["by_category"].get(k, 0),
                                       "sub_counts": {s: report["pois"]["by_sub_category"].get(f"{k}/{s}", 0)
                                                      for s in cats[k]["sub_categories"]},
                                       **({"file": files[k]} if files else {})} for k in cats],
                       "note": "seed/poi_categories.yaml에 있는 업종만 싣는다. 은행은 원자료에 없음",
                       **({} if files else {"file": "pois.geojson"})}
    mp = update_manifest(entries, remove={"schools", "stations", "bus_stops", "bus_routes", "pois"})

    report["sizes"] = sizes
    report["sha256"] = {k: sha256(OUT / k)[:16] for k in sorted(sizes)} | {"manifest.json": sha256(mp)[:16]}
    report["seconds_total"] = round(time.time() - t0, 1)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    sf = report["sdsc_fetch"]
    log(f"상가 API: 호출 {sf['calls']}회 · {sf['seconds']:.1f}초 · 캐시 {sf['cached']}쪽 · 전체 {sf['pages']}쪽 {sf['total_count']:,}건 (stdrYm {sf['stdrYm']})")
    for k in ("schools", "stations", "bus", "pois"):
        r = report[k]
        log(f"{k}: {r['count']}건 · 제외 {r.get('excluded')} · 범위 밖 {r.get('excluded_outside', {})}")
    b = report["bus"]
    log(f"노선 연결: 전체 {b['link_rate_all']['num']:,}/{b['link_rate_all']['den']:,} · 강남 정류장 "
        f"{b['link_rate_gangnam']['num']}/{b['link_rate_gangnam']['den']} · 버린 행 {b['route_stop_rows_dropped']} · 노선 {b['routes']}개")
    far = [r for r in b["station_check"] if not r["within_300m"]]
    log(f"정류장 300m 검증: {len(b['station_check'])}곳 중 300m 초과 {len(far)}곳")
    for k, v in sorted(sizes.items()):
        log(f"  {k}: {v:,} B sha256 {report['sha256'][k]}")
    log(f"manifest.json sha256 {report['sha256']['manifest.json']} · 리포트 build/pois_report.json · {report['seconds_total']}초")
    sync_server_data.sync(quiet=True)    # 서버가 읽는 사본 (P20-B, core/paths.py)


if __name__ == "__main__":
    main()
