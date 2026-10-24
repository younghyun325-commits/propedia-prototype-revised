"""주소 정규화·PNU 생성 (빌드·조회 공통, agents.md §8-6, §10-3). 표준 라이브러리만 사용."""
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
