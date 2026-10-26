"""도로명주소 검색 → PNU (feedback2.md §3-1). juso가 안 되면 브이월드 검색(도로명)으로 대체한다.

결과: {"status": "ok"|"empty"|"error", "via": "juso"|"vworld-search", "error_code", "results": [ROW]}
ROW = {"road_address", "jibun_address", "pnu", "sgg_name", "bjd_code", "bld_name", "lat", "lon"}
"""
import re

from core.address import compact, make_pnu
from core.live import vworld
from core.live.http import LiveError, TTLCache, env_key, get_json

URL = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
KEY_ERRORS = {"E0001", "E0014"}           # 승인키 오류·개발키 기간 만료 → 예비 키로 한 번 더
_BAD = re.compile(r"[%=><\[\]]")
_cache = TTLCache()


def pnu_from_row(row: dict) -> str | None:
    try:
        return make_pnu(row["admCd"], int(row.get("lnbrMnnm") or 0), int(row.get("lnbrSlno") or 0),
                        str(row.get("mtYn", "0")) == "1")
    except (KeyError, TypeError, ValueError):
        return None


def parse_juso(j: dict) -> dict:
    com = ((j or {}).get("results") or {}).get("common") or {}
    code = str(com.get("errorCode", ""))
    if code != "0":
        return {"status": "error", "via": "juso", "error_code": code or "unknown", "results": []}
    rows = ((j.get("results") or {}).get("juso")) or []
    out = []
    for r in rows:
        pnu = pnu_from_row(r)
        if not pnu:
            continue
        out.append({"road_address": r.get("roadAddrPart1") or r.get("roadAddr"), "jibun_address": r.get("jibunAddr"),
                    "pnu": pnu, "sgg_name": r.get("sggNm"), "bjd_code": r.get("admCd"),
                    "bld_name": r.get("bdNm") or None, "lat": None, "lon": None})
    return {"status": "ok" if out else "empty", "via": "juso", "error_code": None, "results": out}


def _juso(keyword: str, fetch) -> dict:
    keys = [k for k in (env_key("JUSO_CONFM_KEY"), env_key("JUSO_CONFM_KEY_ALT")) if k]
    if not keys:
        return {"status": "error", "via": "juso", "error_code": "NO_KEY", "results": []}
    res = {"status": "error", "via": "juso", "error_code": "unknown", "results": []}
    for k in keys:
        try:
            res = parse_juso(fetch(URL, {"confmKey": k, "currentPage": 1, "countPerPage": 5, "keyword": keyword,
                                         "resultType": "json"}))
        except LiveError as e:
            res = {"status": "error", "via": "juso", "error_code": str(e), "results": []}
        if res["status"] != "error" or res["error_code"] not in KEY_ERRORS:
            break
    return res


def _from_vworld(keyword: str, fetch) -> dict:
    items = vworld.search_road(keyword, fetch=fetch)
    if items is None:
        return {"status": "error", "via": "vworld-search", "error_code": "vworld", "results": []}
    out = []
    for it in items:
        road = it["road_address"] or ""
        m = re.search(r"\s([가-힣]+구)\s", " " + road + " ")
        out.append({"road_address": re.sub(r"\s*\(.*\)\s*$", "", road), "jibun_address": it["parcel"],
                    "pnu": it["pnu"], "sgg_name": m.group(1) if m else None, "bjd_code": it["pnu"][:10],
                    "bld_name": it["bld_name"], "lat": it["lat"], "lon": it["lon"]})
    return {"status": "ok" if out else "empty", "via": "vworld-search", "error_code": None, "results": out}


def search(keyword: str, *, fetch=None, fallback: bool = True) -> dict:
    """도로명(또는 건물명 포함) 검색. 메모리 캐시 1시간. juso 오류면 브이월드 검색으로 대체."""
    q = _BAD.sub(" ", keyword or "").strip()
    if not q:
        return {"status": "empty", "via": "juso", "error_code": None, "results": []}
    ck = compact(q)
    hit = _cache.get(ck)
    if hit:
        return hit
    fetch = fetch or get_json
    res = _juso(q, fetch)
    if res["status"] == "error" and fallback:
        alt = _from_vworld(q, fetch)
        if alt["status"] != "error":
            alt["juso_error"] = res["error_code"]
            res = alt
    if res["status"] != "error":
        _cache.put(ck, res)
    return res
