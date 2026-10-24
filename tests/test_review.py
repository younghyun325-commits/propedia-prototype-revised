from conftest import parcel_review_id
from core.lookup import lookup

A1 = "강남구 압구정동 527"


def inc(resp):
    return resp["layers"]["parcel"]["included_projects"]


def test_no_decisions_original(con):
    r = lookup(con, A1, decisions=[])
    assert [p["inclusion"] for p in inc(r)] == ["possible"]
    assert r["review_applied"] == [] and r["events"] == []


def test_parcel_approve_included(con):
    rid = parcel_review_id(con)
    r = lookup(con, A1, decisions=[{"review_id": rid, "action": "approve"}])
    assert [(p["inclusion"], p["basis"]) for p in inc(r)] == [("included", "manual_review")]
    assert inc(r)[0]["message"].startswith("이 필지는 ")
    assert r["events"][0]["event_type"] == "review_decision" and r["events"][0]["action"] == "approve"


def test_parcel_reject_removed(con):
    rid = parcel_review_id(con)
    r = lookup(con, A1, decisions=[{"review_id": rid, "action": "reject"}])
    assert inc(r) == []
    # 필지에서 빠진 사업은 같은 법정동 사업 목록에 나온다
    assert [p["project_id"] for p in r["layers"]["dong"]["projects"]] == [1]


def test_last_decision_wins(con):
    rid = parcel_review_id(con)
    r = lookup(con, A1, decisions=[{"review_id": rid, "action": "reject"}, {"review_id": rid, "action": "approve"}])
    assert [p["inclusion"] for p in inc(r)] == ["included"]


def test_unknown_review_id_ignored(con):
    r = lookup(con, A1, decisions=[{"review_id": 99999, "action": "approve"}])
    assert r["review_applied"] == [{"review_id": 99999, "ignored": "없는 검수 항목"}]
    assert [p["inclusion"] for p in inc(r)] == ["possible"]


def test_bad_action_ignored(con):
    rid = parcel_review_id(con)
    r = lookup(con, A1, decisions=[{"review_id": rid, "action": "edit"}])
    assert "ignored" in r["review_applied"][0]
    assert [p["inclusion"] for p in inc(r)] == ["possible"]


def _item_review(con, item_key):
    return con.execute("SELECT id FROM review_queue WHERE ref_key=? AND ref_table='applicability_rules'",
                       (item_key,)).fetchone()["id"]


def test_item_reject_removed(con):
    rid = _item_review(con, "D2-04")
    keys = {i["item_key"] for i in lookup(con, A1, decisions=[{"review_id": rid, "action": "reject"}])
            ["layers"]["dong"]["items"]}
    assert "D2-04" not in keys and "D2-05" in keys


def test_item_approve_clears_flag(con):
    rid = _item_review(con, "D2-04")
    items = lookup(con, A1, decisions=[{"review_id": rid, "action": "approve"}])["layers"]["dong"]["items"]
    d = next(i for i in items if i["item_key"] == "D2-04")
    assert d["needs_review"] is False


def test_item_edit_moves_scope(con):
    rid = _item_review(con, "D2-04")
    dec = [{"review_id": rid, "action": "edit",
            "edits": {"summary": "수정한 요약", "scope_type": "BJD", "scope_ref": ["1168010100"]}}]
    a1 = lookup(con, A1, decisions=dec)["layers"]["dong"]["items"]
    assert "D2-04" not in {i["item_key"] for i in a1}
    yeoksam = lookup(con, "강남구 역삼동 737", decisions=dec)["layers"]["dong"]["items"]
    d = next(i for i in yeoksam if i["item_key"] == "D2-04")
    assert d["summary"] == "수정한 요약" and d["edited"] is True
