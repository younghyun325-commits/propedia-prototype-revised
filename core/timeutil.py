"""날짜 유틸 (agents.md §10-2). Windows에 tzdata가 없어도 동작하도록 고정 오프셋을 쓴다."""
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def today_kst() -> date:
    return datetime.now(KST).date()


def d_day(due: date, today: date) -> tuple[int, str]:
    n = (due - today).days
    return n, (f"D-{n}" if n > 0 else "D-day" if n == 0 else f"마감({due.isoformat()})")


def parse_date(s) -> date | None:
    if not s:
        return None
    if isinstance(s, date):
        return s
    return date.fromisoformat(str(s)[:10])
