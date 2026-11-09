"""지도 빌드 공통 (docs/map/PLAN.md P13): 브이월드 2D 데이터 조회·캐시, 좌표계 변환, GeoJSON 쓰기.

- 키: VWORLD_API_KEY, 비어 있으면 VWORLD_API_KEY_DEV (pipeline/build_map_base.py와 같은 규칙). 값은 출력하지 않는다.
- domain: VWORLD_DOMAIN (core/live/vworld.domain()).
- 원 응답은 build/vworld_raw/ 아래에만 둔다 (커밋 안 함). 응답에 키 문자열이 있으면 저장하지 않는다.
- 면적·거리는 EPSG:5186 (Korea 2000 중부원점), 저장은 EPSG:4326 소수 6자리.
"""
import json
import time
from pathlib import Path

import httpx
from pyproj import Transformer
import shapely
from shapely.geometry import mapping, shape

from core.live.vworld import domain as vworld_domain
from pipeline.build_map_base import api_key
from pipeline.common import BUILD, fail

DATA_URL = "https://api.vworld.kr/req/data"
RAW = BUILD / "vworld_raw"

_TO_5186 = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True)
_TO_4326 = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)


def to_5186(geom):
    return shapely.transform(geom, lambda x, y: _TO_5186.transform(x, y), interleaved=False)


def to_4326(geom):
    return shapely.transform(geom, lambda x, y: _TO_4326.transform(x, y), interleaved=False)


def lonlat_to_5186(lon: float, lat: float) -> tuple[float, float]:
    return _TO_5186.transform(lon, lat)


def xy_to_lonlat(x: float, y: float) -> tuple[float, float]:
    return _TO_4326.transform(x, y)


class Stats:
    requests = 0
    seconds = 0.0


def get_feature(data: str, cache: Path, *, refresh: bool = False, **params) -> dict:
    """2D 데이터 GetFeature 1회(여러 쪽이면 모두). cache가 있으면 네트워크를 쓰지 않는다."""
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    key = api_key()
    feats, page, status = [], 1, "OK"
    with httpx.Client(timeout=30) as c:
        while True:
            t0 = time.perf_counter()
            try:
                r = c.get(DATA_URL, params={"service": "data", "request": "GetFeature", "version": "2.0",
                                            "data": data, "crs": "EPSG:4326", "format": "json", "size": 1000,
                                            "page": page, "geometry": "true", "attribute": "true",
                                            "key": key, "domain": vworld_domain(), **params})
            except httpx.HTTPError as e:
                fail(f"{data}: 요청 실패 ({type(e).__name__})")
            Stats.requests += 1
            Stats.seconds += time.perf_counter() - t0
            if r.status_code != 200:
                fail(f"{data}: HTTP {r.status_code}")
            resp = (r.json().get("response") or {})
            status = resp.get("status")
            if status == "NOT_FOUND":
                break
            if status != "OK":
                err = resp.get("error") or {}
                fail(f"{data}: status={status} code={err.get('code')} ({str(err.get('text', ''))[:60]})")
            feats += resp["result"]["featureCollection"]["features"]
            if page >= int((resp.get("page") or {}).get("total") or 1):
                break
            page += 1
    out = {"status": status, "features": feats}
    text = json.dumps(out, ensure_ascii=False, sort_keys=True)
    if key in text:
        fail(f"{data}: 응답에 키 문자열이 들어 있어 저장하지 않습니다")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return out


def rnd(coords, nd: int = 6):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], nd), round(coords[1], nd)]
    return [rnd(c, nd) for c in coords]


def geom_out(geom) -> dict:
    """shapely(4326) → GeoJSON dict, 소수 6자리."""
    m = mapping(geom)
    return {"type": m["type"], "coordinates": rnd(json.loads(json.dumps(m["coordinates"])))}


def geom_in(g: dict):
    return shape(g)


def write_fc(path: Path, features: list[dict], **extra) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "crs": "EPSG:4326", **extra, "features": features}
    path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")
