"""규제 고시 화면용 문구 (P22-1, 요청 13). 지도 화면의 상단 칩·필지 패널·규제 인스펙터가 모두 여기서 읽는다.

원문 제목(applicability_rules.title, extractions/*.json)과 문서 짧은 제목(documents.short_title)은 고치지 않는다.
여기 있는 문구는 그 항목의 원문 근거(evidence·more_evidence·target_note)에 적힌 사실만 옮긴 것이다.
- chip: 상단 칩 (짧게)
- title: 필지 패널 '걸린 고시'와 규제 인스펙터 제목
- basis: 이 문구의 근거 (문서·쪽)
목록에 없는 항목은 chip = 문서 짧은 제목, title = 원문 제목 그대로다.
"""

SEOUL_25 = "서울 25개 구 전체"
SEOUL_25_DETAIL = "서울 25개 구 전체 (기존 4개 구 + 21개 구 신규, 2025.10.16부터)"

DISPLAY: dict[str, dict[str, str]] = {
    "D7-01": {
        "chip": f"조정대상지역 · {SEOUL_25}",
        "title": f"조정대상지역: {SEOUL_25_DETAIL}",
        "basis": "D7 p1 신규 지정 대상지역·지정기간, p2 현황표 '강남구, 서초구, 송파구, 용산구 좌동'",
    },
    "D8-01": {
        "chip": f"투기과열지구 · {SEOUL_25}",
        "title": f"투기과열지구: {SEOUL_25_DETAIL}",
        "basis": "D8 p5 현황표 '강남·서초·송파·용산(’17.8.3)', 나머지 21개 구 ’25.10.16",
    },
}


def chip_label(item_key: str, short_title: str | None) -> str | None:
    d = DISPLAY.get(item_key)
    return d["chip"] if d else short_title


def display_title(item_key: str, title: str | None) -> str | None:
    d = DISPLAY.get(item_key)
    return d["title"] if d else title


def display_basis(item_key: str) -> str | None:
    d = DISPLAY.get(item_key)
    return d["basis"] if d else None
