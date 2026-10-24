def test_one_project_rb02(con):
    rows = con.execute("SELECT project_key, sub_stage_code, stage_as_of, stage_rule FROM projects").fetchall()
    assert len(rows) == 1
    assert tuple(rows[0]) == ("apgujeong-6-1-hanyang7", "RB02", "2026-10-06", "R1")


def test_deadline(con):
    rows = con.execute("SELECT kind, starts_on, due_on FROM deadlines").fetchall()
    assert [tuple(r) for r in rows] == [("public_review", "2026-10-06", "2026-11-06")]


def test_change_events_only_step4(con):
    rows = con.execute("SELECT step, event_type FROM change_events ORDER BY step, id").fetchall()
    assert [tuple(r) for r in rows] == [(4, "new_project"), (4, "deadline_added")]


def test_review_queue_parcel_inclusion(con):
    rows = con.execute("SELECT ref_key FROM review_queue WHERE item_type='parcel_inclusion'").fetchall()
    assert [r["ref_key"] for r in rows] == ["1:1168011000105270000"]


def test_project_parcel_representative(con):
    r = con.execute("SELECT pnu, basis, verified FROM project_parcels").fetchone()
    assert tuple(r) == ("1168011000105270000", "representative_only", 0)


def test_stage_templates_from_plan(con):
    rows = con.execute("SELECT seq, sub_stage_code, title, what_happens, reviewed_by FROM stage_templates "
                       "WHERE project_type='rebuild' ORDER BY seq").fetchall()
    assert len(rows) == 13
    assert rows[0]["title"] == "재건축진단" and rows[1]["sub_stage_code"] == "RB02"
    assert all(r["what_happens"] is None and r["reviewed_by"] is None for r in rows)


def test_all_evidence_ok(con):
    ok, total = con.execute("SELECT sum(evidence_ok_count), sum(evidence_total) FROM extractions").fetchone()
    assert total > 0 and ok == total
