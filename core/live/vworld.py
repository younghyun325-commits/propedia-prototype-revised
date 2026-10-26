"""브이월드 토지 정보·좌표 (feedback2.md §3-2). 토지소유정보 API는 쓰지 않는다 (개인정보).

응답 키 이름은 L0 점검(2026-10-26) 실제 응답으로 확인했다:
- getLandUseAttr → landUses.field[]: prposAreaDstrcCodeNm(용도지역지구명), cnflcAtNm(포함/저촉/접함)
- getLandCharacteristics → landCharacteristicss.field[]: lndcgrCodeNm(지목), lndpclAr(면적), prposArea1Nm(용도지역),
  ladUseSittnNm(이용상황), tpgrphHgCodeNm·tpgrphFrmCodeNm(지형), roadSideCodeNm(도로접면), stdrYear
- getIndvdLandPriceAttr → indvdLandPrices.field[]: pblntfPclnd(원/㎡), stdrYear, pblntfDe(공시일)
- req/address getcoord(type=parcel) → response.result.point.x/y, response.refined.structure.level4LC(PNU)
- req/search(type=address, category=road) → response.result.items[].id(PNU), address.parcel, point
토지이용계획 응답에는 '관련 법률' 칸이 없다.
"""
from core.live.http import LiveError, TTLCache, env_key, get_json, now_kst

NED = "https://api.vworld.kr/ned/data"
ADDRESS_URL = "https://api.vworld.kr/req/address"
SEARCH_URL = "https://api.vworld.kr/req/search"
KEY_ENV = "VWORLD_API_KEY"
DOMAIN = "https://propedia-pretotype.vercel.app"     # 인증키에 등록한 서비스 URL (로컬도 같은 값)
SOURCE = "브이월드(국토교통부 공간정보 오픈플랫폼)"
NOTE = "토지이음 토지이용계획확인서와 같은 원천 자료이며 참고용입니다"
MISSING = "불러오지 못함"
UNAVAILABLE_NOTE = "토지 정보를 지금 불러오지 못했습니다"
NOT_FOUND_NOTE = "브이월드 토지 정보에 이 지번이 없습니다. 지번을 확인해 주세요"
NO_KEY_NOTE = "토지 정보 조회 키가 설정되지 않아 불러오지 못했습니다"

_land_cache = TTLCache()


def _params(key: str, **kw) -> dict:
    return {"key": key, "domain": DOMAIN, "format": "json", **kw}


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


def _num(v):
    try:
        x = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return int(x) if x.is_integer() else x


def _call(fetch, op: str, key: str, **kw) -> list[dict] | None:
    try:
        return ned_records(fetch(f"{NED}/{op}", _params(key, **kw)))
    except LiveError:
        return None


def _by_year(fetch, op: str, key: str, pnu: str, year: int) -> list[dict] | None:
    """올해 기준으로 먼저, 없으면 작년으로 한 번 더 (feedback2.md §3-2)."""
    recs = _call(fetch, op, key, pnu=pnu, stdrYear=year, numOfRows=10, pageNo=1)
    if recs == []:
        recs = _call(fetch, op, key, pnu=pnu, stdrYear=year - 1, numOfRows=10, pageNo=1)
    return recs


def geocode_parcel(address: str, *, fetch=None, key: str | None = None) -> dict | None:
    """지번 주소 → {lat, lon, pnu, source}. 못 찾으면 None."""
    fetch = fetch or get_json
    key = key if key is not None else env_key(KEY_ENV)
    if not key or not address:
        return None
    try:
        j = fetch(ADDRESS_URL, {"service": "address", "request": "getcoord", "version": "2.0", "crs": "epsg:4326",
                                "type": "parcel", "address": address, "format": "json", "key": key,
                                "domain": DOMAIN})
    except LiveError:
        return None
    resp = (j or {}).get("response") or {}
    if resp.get("status") != "OK":
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
                               "key": key, "domain": DOMAIN})
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


def get_land(pnu: str, jibun_address: str | None, *, fetch=None, now=None, use_cache: bool = True) -> dict:
    """PNU → land 블록. 메모리 캐시(1시간) → 실시간. 실패해도 예외 없이 status로 알린다."""
    if use_cache:
        hit = _land_cache.get(pnu)
        if hit:
            return dict(hit, from_cache=True)
    key = env_key(KEY_ENV)
    if not key:
        return unavailable(pnu, NO_KEY_NOTE)
    fetch = fetch or get_json
    now = now or now_kst()
    uses = _call(fetch, "getLandUseAttr", key, pnu=pnu, numOfRows=1000, pageNo=1)
    chars = _by_year(fetch, "getLandCharacteristics", key, pnu, now.year)
    prices = _by_year(fetch, "getIndvdLandPriceAttr", key, pnu, now.year)
    loc = geocode_parcel(jibun_address, fetch=fetch, key=key) if jibun_address else None
    land = build_land(pnu, uses, chars, prices, loc, now.isoformat(timespec="seconds"))
    land["found"] = None if None in (uses, chars, prices) else bool(uses or chars or prices)
    if land["found"] is False:          # 세 API 모두 '결과 0건' (오류 아님) → 그런 지번이 없다
        land["note"] = NOT_FOUND_NOTE
    if land["status"] != "unavailable" and use_cache:
        _land_cache.put(pnu, land)
    return land
