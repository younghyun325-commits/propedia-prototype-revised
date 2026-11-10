"""국토교통부 아파트 매매 실거래가 상세 응답(XML) 파싱 (docs/map/PLAN.md P17 2-1). 순수 함수 — tests/test_rtms_parse.py.

필드 이름은 1단계 실제 응답으로 확인했다 (tests/fixtures/rtms/trade_202610_p1.xml).
- 개인 정보 성격 필드(DROP_FIELDS)는 파싱 단계에서 버린다. DB·GeoJSON·견본에 들어가지 않는다.
- 빈 값은 응답에 공백 한 칸(' ')으로 오므로 strip 후 '' → None.
"""
import hashlib
import re
import xml.etree.ElementTree as ET

OK_CODES = {"000", "00"}
DROP_FIELDS = frozenset({"buyerGbn", "slerGbn", "estateAgentSggNm"})

# raw_hash에 넣는 저장 필드 (순서 고정, 바꾸면 해시가 모두 바뀐다)
STORE_FIELDS = ("sgg_cd", "umd_cd", "land_cd", "bonbun", "bubun", "apt_seq", "apt_name_raw", "umd_name", "jibun",
                "apt_dong", "exclusive_area_m2", "contract_date", "amount_10k_won", "floor", "build_year",
                "deal_type", "land_leasehold", "is_cancelled", "cancelled_date", "registered_date")


class RtmsError(Exception):
    """결과 코드가 정상이 아님 (한도 초과 포함)"""

    def __init__(self, code: str, msg: str):
        super().__init__(f"{code} {msg}")
        self.code, self.msg = code, msg


def _s(v) -> str | None:
    v = (v or "").strip()
    return v or None


def parse_xml(body: str) -> tuple[dict, list[dict]]:
    """→ (머리 {resultCode, resultMsg, totalCount, pageNo, numOfRows}, 항목 원본 dict 목록 — DROP_FIELDS 제외)"""
    root = ET.fromstring(body)
    head = {e.tag: (e.text or "").strip() for e in root.iter()
            if e.tag in ("resultCode", "resultMsg", "numOfRows", "pageNo", "totalCount", "returnReasonCode",
                         "returnAuthMsg", "errMsg")}
    items = [{c.tag: _s(c.text) for c in it if c.tag not in DROP_FIELDS} for it in root.iter("item")]
    return head, items


def check_head(head: dict) -> None:
    code = head.get("resultCode") or head.get("returnReasonCode") or ""
    if code not in OK_CODES:
        raise RtmsError(code or "?", head.get("resultMsg") or head.get("returnAuthMsg") or head.get("errMsg") or "")


def amount(v: str | None) -> int | None:
    """'319,000' → 319000 (만원)"""
    v = (v or "").replace(",", "").strip()
    return int(v) if v.isdigit() else None


def ymd(y, m, d) -> str | None:
    try:
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except (TypeError, ValueError):
        return None


_SHORT = re.compile(r"^(\d{2})\.(\d{1,2})\.(\d{1,2})$")


def short_date(v: str | None) -> str | None:
    """'26.11.03' → '2026-11-03' (두 자리 연도는 20YY). 'YYYY.MM.DD'·'YYYYMMDD'도 받는다."""
    v = (v or "").strip()
    if not v:
        return None
    m = _SHORT.match(v)
    if m:
        return ymd(2000 + int(m.group(1)), m.group(2), m.group(3))
    m = re.match(r"^(\d{4})[.\-]?(\d{1,2})[.\-]?(\d{1,2})$", v)
    return ymd(*m.groups()) if m else None


def pnu(sgg: str | None, umd: str | None, land: str | None, bon: str | None, bu: str | None) -> tuple[str | None, str | None]:
    """→ (19자리 PNU, 실패 사유). 자리 수를 채우지 않는다: 본번·부번만 4자리로 맞춘다 (숫자일 때)."""
    parts = {"sggCd": sgg, "umdCd": umd, "landCd": land, "bonbun": bon, "bubun": bu}
    miss = [k for k, v in parts.items() if not v]
    if miss:
        return None, "없음: " + ",".join(miss)
    if not all(v.isdigit() for v in parts.values()):
        return None, "숫자 아님"
    if len(sgg) != 5 or len(umd) != 5 or len(land) != 1 or len(bon) > 4 or len(bu) > 4:
        return None, f"자리 수 (sgg {len(sgg)}·umd {len(umd)}·land {len(land)}·bon {len(bon)}·bu {len(bu)})"
    if land not in ("1", "2"):
        return None, f"landCd {land}"
    return f"{sgg}{umd}{land}{int(bon):04d}{int(bu):04d}", None


def floor_(v: str | None) -> int | None:
    try:
        return int((v or "").strip())
    except ValueError:
        return None


def area(v: str | None) -> float | None:
    try:
        return round(float((v or "").strip()), 2)
    except ValueError:
        return None


def raw_hash(rec: dict, occurrence: int = 0) -> str:
    """저장 필드를 정해진 순서로 이은 문자열의 sha256. 같은 달 응답 안에서 저장 필드가 모두 같은 레코드가 또 나오면
    (2021년 전 동 표기가 없을 때 등, 서로 다른 거래로 본다) 두 번째부터 '#n'을 붙인다."""
    s = "\x1f".join("" if rec.get(k) is None else str(rec[k]) for k in STORE_FIELDS)
    if occurrence:
        s += f"\x1f#{occurrence}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def number_same(recs: list[dict]) -> int:
    """한 달 응답의 레코드 목록에서 raw_hash가 같은 레코드에 순번을 붙인다 (제자리 수정). → 순번을 붙인 수"""
    seen: dict[str, int] = {}
    n = 0
    for r in recs:
        base = r["raw_hash"]
        k = seen.get(base, 0)
        seen[base] = k + 1
        if k:
            r["raw_hash"] = raw_hash(r, k)
            n += 1
    return n


def record(it: dict) -> dict:
    """응답 항목 1건 → 저장 레코드 (DROP_FIELDS 없음). pnu_reason은 저장하지 않는 진단값."""
    p, why = pnu(it.get("sggCd"), it.get("umdCd"), it.get("landCd"), it.get("bonbun"), it.get("bubun"))
    cancelled = (it.get("cdealType") or "").upper() == "O"
    rec = {
        "sgg_cd": it.get("sggCd"), "umd_cd": it.get("umdCd"), "land_cd": it.get("landCd"),
        "bonbun": it.get("bonbun"), "bubun": it.get("bubun"),
        "apt_seq": it.get("aptSeq"), "apt_name_raw": it.get("aptNm"), "umd_name": it.get("umdNm"),
        "jibun": it.get("jibun"), "apt_dong": it.get("aptDong"),
        "exclusive_area_m2": area(it.get("excluUseAr")),
        "contract_date": ymd(it.get("dealYear"), it.get("dealMonth"), it.get("dealDay")),
        "amount_10k_won": amount(it.get("dealAmount")),
        "floor": floor_(it.get("floor")),
        "build_year": int(it["buildYear"]) if (it.get("buildYear") or "").isdigit() else None,
        "deal_type": it.get("dealingGbn"), "land_leasehold": it.get("landLeaseholdGbn"),
        "is_cancelled": 1 if cancelled else 0,
        "cancelled_date": short_date(it.get("cdealDay")) if cancelled else None,
        "registered_date": short_date(it.get("rgstDate")),
    }
    rec["pnu"] = p
    rec["pnu_reason"] = why
    rec["raw_hash"] = raw_hash(rec)
    return rec
