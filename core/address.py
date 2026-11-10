"""주소 정규화·PNU 생성 (빌드·조회 공통, agents.md §8-6, §10-3). 표준 라이브러리만 사용."""
import json
import re

JIBUN_RE = re.compile(
    r"^\s*(?:서울(?:특별시|시)?\s*)?(?P<gu>[가-힣]+구)\s*(?P<dong>[가-힣0-9]+동)\s*"
    r"(?P<san>산\s*)?(?P<main>\d{1,4})(?:\s*-\s*(?P<sub>\d{1,4}))?\s*(?:번지)?\s*$")

SCOPE_GU = "강남구"
SCOPE_SGG = "11680"


def make_pnu(bjd_code: str, main: int, sub: int = 0, san: bool = False) -> str:
    return f"{bjd_code}{'2' if san else '1'}{main:04d}{sub:04d}"


def parse_jibun(text: str) -> dict | None:
    """지번 주소 문자열을 {gu, dong, san, main, sub}로 나눈다. 형식이 아니면 None."""
    m = JIBUN_RE.match(text or "")
    if not m:
        return None
    return {
        "gu": m.group("gu"),
        "dong": m.group("dong"),
        "san": bool(m.group("san")),
        "main": int(m.group("main")),
        "sub": int(m.group("sub") or 0),
    }


def pnu_from_juso(row: dict) -> str:
    """도로명주소 API 응답 1행 → PNU (admCd + 산 구분 + 본번 + 부번)."""
    san = str(row.get("mtYn", "0")) == "1"
    return make_pnu(row["admCd"], int(row.get("lnbrMnnm") or 0), int(row.get("lnbrSlno") or 0), san)


def compact(text: str) -> str:
    """도로명·지번 주소 비교용: 서울특별시/서울시 → 서울, 공백 제거."""
    s = (text or "").replace("서울특별시", "서울").replace("서울시", "서울")
    return re.sub(r"\s+", "", s)


MSG_EMPTY = "주소를 입력해 주세요"
MSG_OUT = "시연 범위(강남구) 밖입니다"
MSG_NOT_FOUND = "시연 주소 목록에서 찾을 수 없습니다. 지번 주소(예: 강남구 압구정동 527)로 입력해 주세요"
MSG_SEARCH_DOWN = "도로명주소 검색을 지금 쓸 수 없습니다. 지번 주소(예: 강남구 일원동 619)로 입력해 주세요"
MSG_NO_RESULT = "주소를 찾지 못했습니다. 강남구 도로명주소나 지번 주소를 입력해 주세요"
MSG_AMBIGUOUS = "주소가 여러 개 찾아졌습니다. 아래에서 하나를 고르세요"
MAX_CANDIDATES = 5
_GU_RE = re.compile(r"([가-힣]+구)(?![가-힣])")

KEYS = ["status", "message", "addr_id", "road_address", "jibun_address", "pnu", "bjd_code", "sgg_code",
        "dong_name", "saenghwal", "lat", "lon", "coord_source", "match_via", "candidates"]


def _result(status: str, message: str | None = None, **kw) -> dict:
    r = {k: None for k in KEYS}
    r.update(status=status, message=message)
    r.update({k: v for k, v in kw.items() if k in r})
    return r


def _dong_info(con, bjd_code: str | None) -> dict:
    if not bjd_code:
        return {}
    row = con.execute("SELECT dong_name, saenghwal FROM bjd_codes WHERE bjd_code=?", (bjd_code,)).fetchone()
    return {"dong_name": row["dong_name"], "saenghwal": row["saenghwal"]} if row else {}


def _from_demo(con, row, via: str = "demo") -> dict:
    if not row["in_scope"]:
        return _result("out_of_scope", MSG_OUT, addr_id=row["addr_id"], road_address=row["road_address"],
                       jibun_address=row["jibun_address"], match_via=via)
    return _result("ok", None, addr_id=row["addr_id"], road_address=row["road_address"],
                   jibun_address=row["jibun_address"], pnu=row["pnu"], bjd_code=row["bjd_code"],
                   sgg_code=row["sgg_code"], lat=row["lat"], lon=row["lon"], coord_source=row["coord_source"],
                   match_via=via, **_dong_info(con, row["bjd_code"]))


def jibun_text(con, pnu: str) -> str | None:
    """PNU → '서울특별시 강남구 일원동 619' (지오코더·화면용). 법정동이 코드표에 없으면 None."""
    b = con.execute("SELECT dong_name FROM bjd_codes WHERE bjd_code=?", (pnu[:10],)).fetchone()
    if b is None:
        return None
    main, sub, san = int(pnu[11:15]), int(pnu[15:19]), pnu[10] == "2"
    return f"서울특별시 {SCOPE_GU} {b['dong_name']} " + ("산 " if san else "") + f"{main}" + (f"-{sub}" if sub else "")


def _demo_by_pnu(con, pnu: str):
    return con.execute("SELECT * FROM demo_addresses WHERE pnu=? AND in_scope=1 ORDER BY addr_id", (pnu,)).fetchone()


def normalize_pnu(con, pnu: str, via: str = "map-click") -> dict:
    """PNU(지도 클릭 등으로 이미 정해진 필지) → 정규화 결과. 시연 주소와 같은 필지면 그 행을 쓴다 (P15)."""
    if not (isinstance(pnu, str) and len(pnu) == 19 and pnu.isdigit()):
        return _result("not_found", "PNU는 숫자 19자리입니다", match_via=via)
    if pnu[:5] != SCOPE_SGG:
        return _result("out_of_scope", MSG_OUT, match_via=via)
    info = _dong_info(con, pnu[:10])
    if not info:
        return _result("out_of_scope", MSG_OUT, match_via=via)
    same = _demo_by_pnu(con, pnu)
    if same:
        return _from_demo(con, same, via)
    return _result("ok", None, jibun_address=jibun_text(con, pnu), pnu=pnu, bjd_code=pnu[:10], sgg_code=pnu[:5],
                   match_via=via, **info)


def _from_search_row(con, r: dict, via: str) -> dict:
    """도로명 검색 결과 1건 → 정규화 결과. 같은 PNU의 시연 주소가 있으면 그 행(캐시·좌표)을 쓴다."""
    pnu = r["pnu"]
    if pnu[:5] != SCOPE_SGG:
        return _result("out_of_scope", MSG_OUT, road_address=r.get("road_address"), match_via=via)
    same = _demo_by_pnu(con, pnu)
    if same:
        res = _from_demo(con, same, via)
        res["road_address"] = r.get("road_address") or res["road_address"]
        return res
    return _result("ok", None, road_address=r.get("road_address"), jibun_address=jibun_text(con, pnu), pnu=pnu,
                   bjd_code=pnu[:10], sgg_code=pnu[:5], match_via=via, **_dong_info(con, pnu[:10]))


def _same_road(found: str | None, typed: str) -> bool:
    """검색 결과 도로명이 입력과 같은 주소인지 ('서울'·'강남구'를 빼고 쓴 입력도 같다고 본다)."""
    a = compact(found).removeprefix("서울")
    b = compact(typed).removeprefix("서울")
    return bool(a) and bool(re.search(r"\d", b)) and (a == b or a.endswith(b))


def _live_search(con, text: str, search) -> dict:
    """③ 도로명주소 실시간 검색 (feedback2.md §3-1)."""
    res = search(text)
    if res["status"] == "error":
        return _result("not_found", MSG_SEARCH_DOWN, match_via=res.get("via"))
    rows = res["results"]
    if not rows:
        return _result("not_found", MSG_NO_RESULT, match_via=res.get("via"))
    gangnam = [r for r in rows if r["pnu"][:5] == SCOPE_SGG]
    if not gangnam:
        return _result("out_of_scope", MSG_OUT, road_address=rows[0].get("road_address"), match_via=res.get("via"))
    first = rows[0]
    if len(rows) == 1 or len(gangnam) == 1 or (first in gangnam and _same_road(first.get("road_address"), text)):
        return _from_search_row(con, first if first in gangnam else gangnam[0], res.get("via"))
    cands = [{"road_address": r.get("road_address"), "jibun_address": jibun_text(con, r["pnu"]), "pnu": r["pnu"],
              "bld_name": r.get("bld_name")} for r in gangnam[:MAX_CANDIDATES]]
    return _result("ambiguous", MSG_AMBIGUOUS, match_via=res.get("via"), candidates=cands)


def normalize(con, text: str, search=None) -> dict:
    """주소 문자열 → 정규화 결과 (agents.md §10-3, feedback2.md §3-1).

    ① 시연 주소 일치 ② 지번 정규식 ③ (search가 있으면) 도로명주소 실시간 검색. search=None이면 네트워크를 쓰지 않는다.
    """
    if not (text or "").strip():
        return _result("not_found", MSG_EMPTY)
    key = compact(text)
    demo = con.execute("SELECT * FROM demo_addresses ORDER BY addr_id").fetchall()
    for row in demo:
        if not row["input_text"]:
            continue          # 키 재발급 대기 중인 빈 행
        cands = [row["input_text"], row["road_address"], row["jibun_address"]]
        try:
            cands += json.loads(row["aliases"] or "[]")
        except ValueError:
            pass
        if any(c and compact(c) == key for c in cands):
            return _from_demo(con, row)

    j = parse_jibun(text)
    if j:
        if j["gu"] != SCOPE_GU:
            return _result("out_of_scope", MSG_OUT)
        b = con.execute("SELECT bjd_code, sgg_code, dong_name, saenghwal FROM bjd_codes WHERE dong_name=?",
                        (j["dong"],)).fetchone()
        if b is None:
            return _result("not_found", f"강남구 법정동 목록에서 '{j['dong']}'을(를) 찾을 수 없습니다")
        pnu = make_pnu(b["bjd_code"], j["main"], j["sub"], j["san"])
        jibun = f"서울특별시 {j['gu']} {j['dong']} " + ("산 " if j["san"] else "") + \
                f"{j['main']}" + (f"-{j['sub']}" if j["sub"] else "")
        same = _demo_by_pnu(con, pnu)
        if same:
            return _from_demo(con, same, "jibun")
        return _result("ok", None, jibun_address=jibun, pnu=pnu, bjd_code=b["bjd_code"], sgg_code=b["sgg_code"],
                       dong_name=b["dong_name"], saenghwal=b["saenghwal"], match_via="jibun")

    for gu in _GU_RE.findall(text):
        if gu != SCOPE_GU:
            return _result("out_of_scope", MSG_OUT)
    if search is not None:
        return _live_search(con, text, search)
    return _result("not_found", MSG_NOT_FOUND)
