"""규제 고시 화면용 문구 (P22-1, 요청 13). 지도 화면의 상단 칩·필지 패널·규제 인스펙터가 모두 여기서 읽는다.

원문 제목(applicability_rules.title, extractions/*.json)과 문서 짧은 제목(documents.short_title)은 고치지 않는다.
여기 있는 문구는 그 항목의 원문 근거(evidence·more_evidence·target_note)에 적힌 사실만 옮긴 것이다.
- chip: 상단 칩 (짧게)
- title: 필지 패널 '걸린 고시'와 규제 인스펙터 제목
- summary: 규제 인스펙터 요약 (없으면 원문 요약)
- basis: 이 문구의 근거 (문서·쪽)
목록에 없는 항목은 chip = 문서 짧은 제목, title = 원문 제목 그대로다.
"""

SEOUL_25 = "서울 25개 구 전체"
SEOUL_25_DETAIL = "서울 25개 구 전체 (기존 4개 구 + 21개 구 신규, 2025.10.16부터)"

DISPLAY: dict[str, dict[str, str]] = {
    "D5-01": {
        "title": "토지거래허가구역 재지정: 압구정 아파트지구 (아파트지구 안 필지만)",
        "basis": "D5 p1 대상지역 '강남구 압구정동 압구정 아파트지구', 면적 1,149,476㎡",
    },
    "D6-01": {
        "summary": "서울 25개 구의 아파트가 허가 대상이에요. 연립·다세대주택은 공고 붙임2 목록의 혼재 단지만 대상이고, "
                   "강남구 단지는 목록에 없어요. 지정기간은 2025.10.20~2026.12.31이에요.",
        "basis": "D6 p1 허가대상 용도와 '붙임2 표에 나열된 지번이 표기된 주택에 한함', p4 붙임2 목록 16곳 (강남구 없음)",
    },
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
    return DISPLAY.get(item_key, {}).get("chip", short_title)


def display_title(item_key: str, title: str | None) -> str | None:
    return DISPLAY.get(item_key, {}).get("title", title)


def display_summary(item_key: str, summary: str | None) -> str | None:
    return DISPLAY.get(item_key, {}).get("summary", summary)


def display_basis(item_key: str) -> str | None:
    return DISPLAY.get(item_key, {}).get("basis")
