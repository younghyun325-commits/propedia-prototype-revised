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
_GU_RE = re.compile(r"([가-힣]+구)(?![가-힣])")

KEYS = ["status", "message", "addr_id", "road_address", "jibun_address", "pnu", "bjd_code", "sgg_code",
        "dong_name", "saenghwal", "lat", "lon", "coord_source"]


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


def _from_demo(con, row) -> dict:
    if not row["in_scope"]:
        return _result("out_of_scope", MSG_OUT, addr_id=row["addr_id"], road_address=row["road_address"],
                       jibun_address=row["jibun_address"])
    return _result("ok", None, addr_id=row["addr_id"], road_address=row["road_address"],
                   jibun_address=row["jibun_address"], pnu=row["pnu"], bjd_code=row["bjd_code"],
                   sgg_code=row["sgg_code"], lat=row["lat"], lon=row["lon"], coord_source=row["coord_source"],
                   **_dong_info(con, row["bjd_code"]))


def normalize(con, text: str) -> dict:
    """주소 문자열 → 정규화 결과 (agents.md §10-3)."""
    if not (text or "").strip():
        return _result("not_found", MSG_EMPTY)
    key = compact(text)
    demo = con.execute("SELECT * FROM demo_addresses ORDER BY CAST(substr(addr_id, 2) AS INTEGER)").fetchall()
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
        same = con.execute("SELECT * FROM demo_addresses WHERE pnu=? AND in_scope=1 "
                           "ORDER BY CAST(substr(addr_id, 2) AS INTEGER)", (pnu,)).fetchone()
        if same:
            r = _from_demo(con, same)
            return r
        return _result("ok", None, jibun_address=jibun, pnu=pnu, bjd_code=b["bjd_code"], sgg_code=b["sgg_code"],
                       dong_name=b["dong_name"], saenghwal=b["saenghwal"])

    for gu in _GU_RE.findall(text):
        if gu != SCOPE_GU:
            return _result("out_of_scope", MSG_OUT)
    return _result("not_found", MSG_NOT_FOUND)
