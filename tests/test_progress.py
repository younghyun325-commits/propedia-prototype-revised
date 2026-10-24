from datetime import date

from core.progress import progress


def test_position_and_next(con):
    p = progress(con, 1, today=date(2026, 10, 25))
    assert p["position_label"] == "재건축 13단계 중 2번째"
    assert p["current"]["code"] == "RB02"
    assert p["next"]["code"] == "RB03"
    assert [s["status"] for s in p["stages"][:3]] == ["done", "current", "upcoming"]
    assert p["stages"][0]["verified"] is False and p["stages"][0]["note"] == "확인된 고시 없음"
    assert len(p["stages"]) == 13


def test_template_texts_from_plan_only(con):
    p = progress(con, 1, today=date(2026, 10, 25))
    assert p["current"]["what_happens"] is None
    assert p["current"]["what_happens_note"] == "단계 설명 문구는 법령 대조 후 사람이 작성합니다"
    assert p["current"]["owner_actions"] == "공람 기간 내 의견 제출"
    assert p["current"]["template_status"] == "법령 대조 전 초안"


def test_d_day_labels(con):
    d = progress(con, 1, today=date(2026, 10, 25))["deadlines"][0]
    assert (d["d_day"], d["d_day_label"], d["status"]) == (12, "D-12", "open")
    d = progress(con, 1, today=date(2026, 11, 6))["deadlines"][0]
    assert d["d_day_label"] == "D-day" and d["status"] == "open"
    d = progress(con, 1, today=date(2026, 11, 7))["deadlines"][0]
    assert d["d_day_label"] == "마감(2026-11-06)" and d["status"] == "closed"


def test_remaining_fixed(con):
    r = progress(con, 1, today=date(2026, 10, 25))["remaining"]
    assert r["note"] == "비교할 사례가 부족합니다"
    assert r["to_next"] is None and r["to_completion"] is None


def test_sources_and_history(con):
    p = progress(con, 1, today=date(2026, 10, 25))
    assert p["stage_basis"]["rule_id"] == "R1" and p["stage_basis"]["source"]["pdf_page"] == 1
    assert len(p["related_history"]) == 5
    dates = [h["date"] for h in p["related_history"]]
    assert dates == sorted(dates)
    assert all(f["evidence_ok"] and f["source"]["page_image"] for f in p["facts"])


def test_unknown_project(con):
    assert progress(con, 999) is None
