"""날짜 유틸 (agents.md §10-2). Windows에 tzdata가 없어도 동작하도록 고정 오프셋을 쓴다."""
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def today_kst() -> date:
    return datetime.now(KST).date()


def d_day(due: date, today: date) -> tuple[int, str]:
    n = (due - today).days
    return n, (f"D-{n}" if n > 0 else "D-day" if n == 0 else f"마감({due.isoformat().replace('-', '.')})")


def parse_date(s) -> date | None:
    if not s:
        return None
    if isinstance(s, date):
        return s
    return date.fromisoformat(str(s)[:10])


def dot(s) -> str:
    """'2026-04-27' → '2026.04.27'"""
    return str(s)[:10].replace("-", ".")


EFFECTIVE_STATUS_LABELS = {"in_force": "효력 기간 중", "ended": "효력 기간 끝남", "not_started": "효력 시작 전"}
# 지도·타임라인용 짧은 라벨 (P19). 판정은 아래 effective() 하나
EFFECTIVE_SHORT_LABELS = {"in_force": "효력 중", "ended": "종료", "not_started": "효력 전"}


def effective(start, end, today: date) -> dict:
    """원문에 적힌 효력 기간과 오늘을 비교한 사실 (feedback.md §2-2-5). 기간이 없으면 상태도 없다."""
    s, e = parse_date(start), parse_date(end)
    if s is None and e is None:
        return {"effective_label": None, "effective_status": None, "effective_status_label": None}
    if s and e:
        label = f"효력 기간 {dot(s)} ~ {dot(e)}"
    elif s:
        label = f"효력 {dot(s)}부터"
    else:
        label = f"효력 {dot(e)}까지"
    status = "not_started" if s and today < s else "ended" if e and today > e else "in_force"
    return {"effective_label": label, "effective_status": status,
            "effective_status_label": EFFECTIVE_STATUS_LABELS[status]}
