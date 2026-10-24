"""텍스트 정규화·근거 문장 검사 (빌드·조회 공통, agents.md §9-4)."""
import re
import unicodedata

_WS = re.compile(r"\s+")
_DOTS = str.maketrans({"ㆍ": "·", "․": "·", "‧": "·", "・": "·"})


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").translate(_DOTS)
    return _WS.sub("", s)


def evidence_in(evidence: str, page_text: str) -> bool:
    e = norm(evidence)
    return len(e) >= 2 and e in norm(page_text)


def squash_ws(s: str) -> str:
    """공백만 한 칸으로 정리한다 (가운뎃점 등은 유지). 단계 판정 규칙(§10-5)에 쓴다."""
    return _WS.sub(" ", unicodedata.normalize("NFC", s or "")).strip()


def unify_dots(s: str) -> str:
    """가운뎃점 변형(ㆍ ․ ‧ ・)을 · (U+00B7)로 통일한다."""
    return unicodedata.normalize("NFC", s or "").translate(_DOTS)
