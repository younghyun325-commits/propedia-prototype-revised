"""브이월드 토지 정보·좌표 (feedback2.md §3-2). 토지소유정보 API는 쓰지 않는다 (개인정보).

응답 키 이름은 L0 점검(2026-10-26) 실제 응답으로 확인했다:
- getLandUseAttr → landUses.field[]: prposAreaDstrcCodeNm(용도지역지구명), cnflcAtNm(포함/저촉/접함)
- getLandCharacteristics → landCharacteristicss.field[]: lndcgrCodeNm(지목), lndpclAr(면적), prposArea1Nm(용도지역),
  ladUseSittnNm(이용상황), tpgrphHgCodeNm·tpgrphFrmCodeNm(지형), roadSideCodeNm(도로접면), stdrYear
- getIndvdLandPriceAttr → indvdLandPrices.field[]: pblntfPclnd(원/㎡), stdrYear, pblntfDe(공시일)
- req/address getcoord(type=parcel) → response.result.point.x/y, response.refined.structure.level4LC(PNU)
- req/search(type=address, category=road) → response.result.items[].id(PNU), address.parcel, point
- req/data(LP_PA_CBND_BUBUN, geomFilter=POINT) → response.result.featureCollection.features[]:
  properties pnu·jibun('737 대')·addr('서울특별시 강남구 역삼동 737')·bonbun·bubun·jiga·gosi_year, geometry MultiPolygon
토지이용계획 응답에는 '관련 법률' 칸이 없다.

필지 점 조회(parcel_at)·PNU 조회(parcel_by_pnu) 결과는 저장하지 않는다 (메모리 캐시도 없음, P15).
"""
from core.geo import centroid
from core.live.http import LiveError, TTLCache, env_key, get_bytes, get_json, now_kst

NED = "https://api.vworld.kr/ned/data"
ADDRESS_URL = "https://api.vworld.kr/req/address"
SEARCH_URL = "https://api.vworld.kr/req/search"
DATA_URL = "https://api.vworld.kr/req/data"
PARCEL_DATA = "LP_PA_CBND_BUBUN"
PARCEL_COORD_SOURCE = "vworld-2d:LP_PA_CBND_BUBUN centroid"
WMS_URL = "https://api.vworld.kr/req/wms"
# 참고 WMS (P15). 이름은 GetCapabilities로 확인 (pipeline/check_wms.py, 2026-11-10). 값 = 최소 타일 줌
WMS_LAYERS = {"lt_c_uq111": 14, "lt_c_upisuq161": 14, "lp_pa_cbnd_bubun": 17}
# 연속지적도 WMS는 0.6m/px보다 거친 요청에 빈 그림(1,784B)을 준다 [확인 2026-11-10: z16 256px 2.39·512px 1.19m/px 빈 그림,
# z17 512px 0.6m/px 그림]. 그래서 이 레이어는 더 큰 그림을 받아 같은 타일 자리에 쓴다 (MapLibre는 큰 그림을 줄여 그림)
WMS_MAX_MPP = {"lp_pa_cbnd_bubun": 0.6}
WMS_TILE_MAX = 512
_R3857 = 20037508.342789244
KEY_ENV = "VWORLD_API_KEY"
DOMAIN_ENV = "VWORLD_DOMAIN"
DEFAULT_DOMAIN = "https://propedia-prototype.vercel.app"     # 운영 키에 등록한 서비스 URL (VWORLD_DOMAIN이 없을 때)
SOURCE = "브이월드(국토교통부 공간정보 오픈플랫폼)"
NOTE = "토지이음 토지이용계획확인서와 같은 원천 자료이며 참고용입니다"
MISSING = "불러오지 못함"
UNAVAILABLE_NOTE = "토지 정보를 지금 불러오지 못했습니다"
NOT_FOUND_NOTE = "브이월드 토지 정보에 이 지번이 없습니다. 지번을 확인해 주세요"
NO_KEY_NOTE = "토지 정보 조회 키가 설정되지 않아 불러오지 못했습니다"
PARCEL_UNAVAILABLE_NOTE = "필지 정보를 지금 불러오지 못했습니다"
PARCEL_TIMEOUT_NOTE = "필지 조회 시간이 초과되었습니다. 다시 눌러 주세요"
PARCEL_NO_KEY_NOTE = "필지 조회 키가 설정되지 않아 불러오지 못했습니다"
PARCEL_NOT_FOUND_NOTE = "이 지점에서 필지를 찾지 못했습니다"
PARCEL_OUTSIDE_NOTE = "강남구 밖입니다. 프리토타입은 강남구 필지만 조회합니다"

_land_cache = TTLCache()


def domain() -> str:
    """요청의 domain 파라미터 = 인증키에 등록한 서비스 URL. 환경변수 VWORLD_DOMAIN, 없으면 운영 주소."""
    return env_key(DOMAIN_ENV) or DEFAULT_DOMAIN


def _params(key: str, **kw) -> dict:
    return {"key": key, "domain": domain(), "format": "json", **kw}


def ned_records(j: dict) -> list[dict] | None:
    """국가중점 API 응답 → field 목록. 결과 없음은 [], 오류는 None. 1건이면 dict로 오기도 한다."""
    if not isinstance(j, dict) or not j:
        return None
    top = next(iter(j.values()))
    if not isinstance(top, dict):
        return None
    code = str(top.get("resultCode") or "")
    if code and code not in ("OK", "INFO-000", "0"):
        return [] if code in ("NODATA_ERROR", "INFO-200") else None
    f = top.get("field")
    if f is None:
        return []
    return [f] if isinstance(f, dict) else list(f)


def ned_error(j) -> str | None:
    """오류 응답의 결과 코드 (예: INCORRECT_KEY). 화면·로그에 이유만 남긴다 (키·URL 없음)."""
    if isinstance(j, dict) and j:
        top = next(iter(j.values()))
        if isinstance(top, dict) and top.get("resultCode"):
            return str(top["resultCode"])
    return "응답 형식 다름"


def _num(v):
    try:
        x = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return int(x) if x.is_integer() else x


def _call(fetch, op: str, key: str, errors: dict | None = None, **kw) -> list[dict] | None:
    try:
        j = fetch(f"{NED}/{op}", _params(key, **kw))
    except LiveError as e:
        if errors is not None:
            errors[op] = str(e)
        return None
    recs = ned_records(j)
    if recs is None and errors is not None:
        errors[op] = ned_error(j)
    return recs


def _by_year(fetch, op: str, key: str, pnu: str, year: int, errors: dict | None = None) -> list[dict] | None:
    """올해 기준으로 먼저, 없으면 작년으로 한 번 더 (feedback2.md §3-2)."""
    recs = _call(fetch, op, key, errors, pnu=pnu, stdrYear=year, numOfRows=10, pageNo=1)
    if recs == []:
        recs = _call(fetch, op, key, errors, pnu=pnu, stdrYear=year - 1, numOfRows=10, pageNo=1)
    return recs


def geocode_parcel(address: str, *, fetch=None, key: str | None = None, errors: dict | None = None) -> dict | None:
    """지번 주소 → {lat, lon, pnu, source}. 못 찾으면 None."""
    fetch = fetch or get_json
    key = key if key is not None else env_key(KEY_ENV)
    if not key or not address:
        return None
    try:
        j = fetch(ADDRESS_URL, {"service": "address", "request": "getcoord", "version": "2.0", "crs": "epsg:4326",
                                "type": "parcel", "address": address, "format": "json", "key": key,
                                "domain": domain()})
    except LiveError as e:
        if errors is not None:
            errors["getcoord"] = str(e)
        return None
    resp = (j or {}).get("response") or {}
    if resp.get("status") != "OK":
        if errors is not None:
            errors["getcoord"] = str(resp.get("status") or "응답 형식 다름") + (
                f" {(resp.get('error') or {}).get('code')}" if resp.get("error") else "")
        return None
    try:
        pt = resp["result"]["point"]
        lat, lon = float(pt["y"]), float(pt["x"])
    except (KeyError, TypeError, ValueError):
        return None
    pnu = ((resp.get("refined") or {}).get("structure") or {}).get("level4LC") or None
    return {"lat": lat, "lon": lon, "pnu": pnu, "source": "vworld-geocoder:parcel"}


def search_road(query: str, *, fetch=None, key: str | None = None, size: int = 5) -> list[dict] | None:
    """도로명주소 검색(브이월드) → [{pnu, road_address, parcel, bld_name, lat, lon}]. juso 대체 경로. 실패하면 None."""
    fetch = fetch or get_json
    key = key if key is not None else env_key(KEY_ENV)
    if not key:
        return None
    try:
        j = fetch(SEARCH_URL, {"service": "search", "request": "search", "version": "2.0", "query": query,
                               "type": "address", "category": "road", "format": "json", "size": size,
                               "key": key, "domain": domain()})
    except LiveError:
        return None
    resp = (j or {}).get("response") or {}
    if resp.get("status") == "NOT_FOUND":
        return []
    if resp.get("status") != "OK":
        return None
    out = []
    for it in ((resp.get("result") or {}).get("items") or []):
        a = it.get("address") or {}
        pid = str(it.get("id") or "")
        if len(pid) != 19 or not pid.isdigit():
            continue
        pt = it.get("point") or {}
        out.append({"pnu": pid, "road_address": a.get("road"), "parcel": a.get("parcel"),
                    "bld_name": a.get("bldnm") or None,
                    "lat": _num(pt.get("y")), "lon": _num(pt.get("x"))})
    return out


def _parcel_result(status: str, note: str | None = None, **kw) -> dict:
    r = {"status": status, "note": note, "pnu": None, "jibun": None, "address": None, "bjd_code": None,
         "boundary": None, "centroid": None, "source": SOURCE, "data": PARCEL_DATA}
    r.update(kw)
    return r


def _parcel_query(params: dict, *, fetch, key: str | None, allowed_bjd, click: tuple | None) -> dict:
    """2D 데이터 연속지적도 GetFeature 1회 → 필지 1건. 실패해도 예외 없이 status로 알린다."""
    fetch = fetch or get_json
    key = key if key is not None else env_key(KEY_ENV)
    if not key:
        return _parcel_result("unavailable", PARCEL_NO_KEY_NOTE, reason="no_key")
    try:
        j = fetch(DATA_URL, {"service": "data", "request": "GetFeature", "version": "2.0", "data": PARCEL_DATA,
                             "crs": "EPSG:4326", "format": "json", "size": 10, "page": 1, "geometry": "true",
                             "attribute": "true", "key": key, "domain": domain(), **params})
    except LiveError as e:
        timeout = "Timeout" in str(e)
        return _parcel_result("timeout" if timeout else "unavailable",
                              PARCEL_TIMEOUT_NOTE if timeout else PARCEL_UNAVAILABLE_NOTE, reason=str(e))
    resp = (j or {}).get("response") or {}
    st = resp.get("status")
    if st == "NOT_FOUND":
        return _parcel_result("not_found", PARCEL_NOT_FOUND_NOTE)
    if st != "OK":
        return _parcel_result("unavailable", PARCEL_UNAVAILABLE_NOTE,
                              reason=str(st or "응답 형식 다름") + (f" {(resp.get('error') or {}).get('code')}"
                                                                if resp.get("error") else ""))
    feats = (((resp.get("result") or {}).get("featureCollection") or {}).get("features")) or []
    feats = [f for f in feats if len(str((f.get("properties") or {}).get("pnu") or "")) == 19]
    if not feats:
        return _parcel_result("not_found", PARCEL_NOT_FOUND_NOTE)
    f = feats[0]
    p = f.get("properties") or {}
    pnu = str(p["pnu"])
    geom = f.get("geometry") or None
    c = centroid(geom) if geom else None
    if c is None and click is not None:
        c = (click[1], click[0])              # 면적 중심이 면 밖이면 누른 점
    base = {"pnu": pnu, "jibun": p.get("jibun") or None, "address": p.get("addr") or None, "bjd_code": pnu[:10],
            "boundary": geom, "centroid": {"lat": c[1], "lon": c[0], "source": PARCEL_COORD_SOURCE} if c else None}
    if allowed_bjd is not None and pnu[:10] not in allowed_bjd:
        return _parcel_result("outside", PARCEL_OUTSIDE_NOTE, **base)
    return _parcel_result("ok", None, **base)


def parcel_at(lat: float, lon: float, *, fetch=None, key: str | None = None, allowed_bjd=None) -> dict:
    """지도에서 누른 점 → 그 점을 포함하는 필지 (연속지적도 점 필터). allowed_bjd 밖이면 status='outside'."""
    return _parcel_query({"geomFilter": f"POINT({lon} {lat})"}, fetch=fetch, key=key, allowed_bjd=allowed_bjd,
                         click=(lat, lon))


def parcel_by_pnu(pnu: str, *, fetch=None, key: str | None = None, allowed_bjd=None) -> dict:
    """PNU → 필지 경계 (URL sel=parcel:{pnu} 복원용)."""
    return _parcel_query({"attrFilter": f"pnu:=:{pnu}"}, fetch=fetch, key=key, allowed_bjd=allowed_bjd, click=None)


def tile_bbox_3857(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """XYZ 타일 → EPSG:3857 범위 (서, 남, 동, 북)."""
    span = 2 * _R3857 / (2 ** z)
    return (-_R3857 + x * span, _R3857 - (y + 1) * span, -_R3857 + (x + 1) * span, _R3857 - y * span)


def wms_size(layer: str, z: int) -> int:
    span = 2 * _R3857 / (2 ** z)
    size = 256
    limit = WMS_MAX_MPP.get(layer)
    while limit and span / size > limit + 1e-6 and size < WMS_TILE_MAX:
        size *= 2
    return size


WMS_SIZES = (256, 512)
WMS_BAD = "허용하지 않는 레이어·타일입니다"


def wms_check(layer: str, z: int, x: int, y: int, size: int | None = None) -> str | None:
    """레이어·줌·타일 번호·그림 크기 검사. 문제가 있으면 한국어 안내, 없으면 None (강남구 범위 검사는 core/map)."""
    if layer not in WMS_LAYERS:
        return "참고 WMS는 용도지역(lt_c_uq111)·지구단위계획구역(lt_c_upisuq161)·지적도(lp_pa_cbnd_bubun)만 받습니다"
    if not (WMS_LAYERS[layer] <= z <= 19) or not (0 <= x < 2 ** z and 0 <= y < 2 ** z):
        return f"이 레이어는 줌 {WMS_LAYERS[layer]}~19 타일만 받습니다"
    if size is not None and size not in WMS_SIZES:
        return "타일 크기는 256 또는 512만 받습니다"
    limit = WMS_MAX_MPP.get(layer)
    if limit and size is not None and (2 * _R3857 / (2 ** z)) / size > limit + 1e-6:
        return "지적도는 줌 17 이상에 해당하는 해상도(0.6m/px 이하)만 받습니다"
    return None


def wms_tile(layer: str, z: int, x: int, y: int, *, size: int | None = None, fetch_bytes=None,
             key: str | None = None) -> dict:
    """참고 WMS 타일 프록시 (브이월드 WMS는 CORS 헤더가 없어 브라우저가 직접 못 받는다). 저장하지 않는다.
    반환 {status: ok|bad_request|unavailable|timeout, content, content_type, note}. note에는 URL·키를 넣지 않는다."""
    bad = wms_check(layer, z, x, y, size)
    if bad:
        return {"status": "bad_request", "content": b"", "content_type": None, "note": bad}
    key = key if key is not None else env_key(KEY_ENV)
    if not key:
        return {"status": "unavailable", "content": b"", "content_type": None, "note": PARCEL_NO_KEY_NOTE}
    fetch_bytes = fetch_bytes or get_bytes
    size = size or wms_size(layer, z)
    w, s, e, n = tile_bbox_3857(z, x, y)
    try:
        body, ctype = fetch_bytes(WMS_URL, {"SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": layer,
                                            "STYLES": layer, "CRS": "EPSG:3857", "BBOX": f"{w},{s},{e},{n}",
                                            "WIDTH": size, "HEIGHT": size, "FORMAT": "image/png",
                                            "TRANSPARENT": "true", "KEY": key, "DOMAIN": domain()})
    except LiveError as err:
        timeout = "Timeout" in str(err)
        return {"status": "timeout" if timeout else "unavailable", "content": b"", "content_type": None,
                "note": "참고 WMS 응답 시간 초과" if timeout else "참고 WMS 응답 오류"}
    if not (ctype or "").startswith("image/png"):
        return {"status": "unavailable", "content": b"", "content_type": None, "note": "응답이 그림이 아님"}
    return {"status": "ok", "content": body, "content_type": ctype.split(";")[0], "note": None}


def _dedupe_zones(recs: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in recs:
        name = (r.get("prposAreaDstrcCodeNm") or "").strip()
        rel = (r.get("cnflcAtNm") or "").strip()
        if not name or (name, rel) in seen:
            continue
        seen.add((name, rel))
        out.append({"name": name, "relation": rel or None, "registered_on": r.get("registDt") or None})
    return out


def build_land(pnu: str, uses, chars, prices, loc, fetched_at: str) -> dict:
    """세 API와 좌표 결과 → land 블록 (feedback2.md §3-2). 값은 응답 그대로, 해석 문구 없음."""
    c = (chars or [None])[0] if chars else None
    p = (prices or [None])[0] if prices else None
    missing = [name for name, v in (("토지이용계획", uses), ("토지특성", c), ("개별공시지가", p), ("좌표", loc))
               if not v]
    ok_parts = 4 - len(missing)
    status = "ok" if not missing else ("unavailable" if ok_parts == 0 else "partial")
    terrain = " · ".join(x for x in ((c or {}).get("tpgrphHgCodeNm"), (c or {}).get("tpgrphFrmCodeNm")) if x) or None
    return {
        "status": status,
        "pnu": pnu,
        "jimok": (c or {}).get("lndcgrCodeNm") or None,
        "area_m2": _num((c or {}).get("lndpclAr")),
        "land_use_zone": (c or {}).get("prposArea1Nm") or None,
        "land_use_zone2": (c or {}).get("prposArea2Nm") if (c or {}).get("prposArea2Nm") not in (None, "", "지정되지않음") else None,
        "zones": _dedupe_zones(uses or []),
        "use_situation": (c or {}).get("ladUseSittnNm") or None,
        "road_side": (c or {}).get("roadSideCodeNm") or None,
        "terrain": terrain,
        "characteristics_year": _num((c or {}).get("stdrYear")),
        "official_price": {"won_per_m2": _num(p.get("pblntfPclnd")), "year": _num(p.get("stdrYear")),
                           "announced_on": p.get("pblntfDe") or None} if p else None,
        "location": {"lat": loc["lat"], "lon": loc["lon"], "source": loc["source"]} if loc else None,
        "missing": missing,
        "source": SOURCE,
        "fetched_at": fetched_at,
        "from_cache": False,
        "note": NOTE if status != "unavailable" else UNAVAILABLE_NOTE,
    }


def unavailable(pnu: str, note: str = UNAVAILABLE_NOTE) -> dict:
    land = build_land(pnu, None, None, None, None, now_kst().isoformat(timespec="seconds"))
    land["note"] = note
    land["found"] = None
    return land


def get_land(pnu: str, jibun_address: str | None, *, fetch=None, now=None, use_cache: bool = True,
             location: dict | None = None) -> dict:
    """PNU → land 블록. 메모리 캐시(1시간) → 실시간. 실패해도 예외 없이 status로 알린다.

    location({lat, lon, source})을 주면 지오코더를 부르지 않고 그 좌표(필지 경계 중심점)를 쓴다 (P15 필지 클릭).
    """
    if use_cache:
        hit = _land_cache.get(pnu)
        if hit:
            return dict(hit, from_cache=True)
    key = env_key(KEY_ENV)
    if not key:
        return unavailable(pnu, NO_KEY_NOTE)
    fetch = fetch or get_json
    now = now or now_kst()
    errors: dict = {}
    uses = _call(fetch, "getLandUseAttr", key, errors, pnu=pnu, numOfRows=1000, pageNo=1)
    chars = _by_year(fetch, "getLandCharacteristics", key, pnu, now.year, errors)
    prices = _by_year(fetch, "getIndvdLandPriceAttr", key, pnu, now.year, errors)
    if location:
        loc = {"lat": location["lat"], "lon": location["lon"], "source": location["source"]}
    else:
        loc = geocode_parcel(jibun_address, fetch=fetch, key=key, errors=errors) if jibun_address else None
    land = build_land(pnu, uses, chars, prices, loc, now.isoformat(timespec="seconds"))
    land["errors"] = errors or None        # 실패 이유 (HTTP 코드·오류 종류·결과 코드만)
    land["found"] = None if None in (uses, chars, prices) else bool(uses or chars or prices)
    if land["found"] is False:          # 세 API 모두 '결과 0건' (오류 아님) → 그런 지번이 없다
        land["note"] = NOT_FOUND_NOTE
    if land["status"] != "unavailable" and use_cache:
        _land_cache.put(pnu, land)
    return land
