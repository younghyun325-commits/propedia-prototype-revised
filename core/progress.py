"""사업 진행상황 (agents.md §10-6, §11-4). 단계 설명·소유자 안내는 stage_templates(사람이 쓴 표)에서만 가져온다."""
from core import review as review_mod
from core.db import loads, meta, source
from core.lookup import DISCLAIMER
from core.timeutil import d_day, parse_date, today_kst

PROJECT_TYPE_LABELS = {"rebuild": "재건축"}
FACT_FIELDS = ["area_m2", "land_use", "households_before", "households_after", "base_allowed_far", "plan_far",
               "legal_max_far"]
TRACK_LABELS = {"unknown": "확인 안 됨", "general": "일반", "shintong": "신속통합기획", "public": "공공"}
WHAT_HAPPENS_NOTE = "단계 설명 문구는 법령 대조 후 사람이 작성합니다"
REMAINING = {
    "to_next": None,
    "to_completion": None,
    "note": "비교할 사례가 부족합니다",
    "method_note": "원 계획은 비슷한 사업들의 단계별 소요 기간(생존분석)으로 범위를 보여줍니다. 프리토타입에는 비교 사례가 없습니다.",
}


def template_status(t) -> str:
    if t["reviewed_by"]:
        return f"검토 완료 ({t['reviewed_by']}, {t['reviewed_at']})"
    return "법령 대조 전 초안"


def progress(con, project_id: int, decisions=None, today=None) -> dict | None:
    today = today or today_kst()
    p = con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if p is None:
        return None
    ov = review_mod.apply(con, decisions)
    m = meta(con)
    tpls = con.execute("SELECT * FROM stage_templates WHERE project_type=? ORDER BY seq",
                       (p["project_type"],)).fetchall()
    cur = next((t for t in tpls if t["sub_stage_code"] == p["sub_stage_code"]), None)
    hist = {h["sub_stage_code"]: h for h in con.execute(
        "SELECT * FROM project_stage_history WHERE project_id=? ORDER BY entered_at", (project_id,))}

    stages = []
    for t in tpls:
        s = {"seq": t["seq"], "code": t["sub_stage_code"], "title": t["title"]}
        h = hist.get(t["sub_stage_code"])
        if t["seq"] < cur["seq"]:
            s["status"] = "done"
            s["verified"] = h is not None
            s["note"] = None if h else "확인된 고시 없음"
            s["source"] = source(con, h["source_doc_id"], h["pdf_page"]) if h else None
        elif t["seq"] == cur["seq"]:
            s["status"] = "current"
            s["verified"] = h is not None
            s["entered_at"] = h["entered_at"] if h else None
            s["source"] = source(con, h["source_doc_id"], h["pdf_page"]) if h else None
        else:
            s["status"] = "upcoming"
        stages.append(s)

    nxt = next((t for t in tpls if t["seq"] == cur["seq"] + 1), None)
    deadlines = []
    for d in con.execute("SELECT * FROM deadlines WHERE project_id=? ORDER BY due_on", (project_id,)):
        due = parse_date(d["due_on"])
        n, label = d_day(due, today)
        deadlines.append({"kind": d["kind"], "title": d["title"], "starts_on": d["starts_on"], "due_on": d["due_on"],
                          "d_day": n, "d_day_label": label, "status": "open" if due >= today else "closed",
                          "how_to_submit": d["how_to_submit"], "places": loads(d["places"], []),
                          "source": source(con, d["source_doc_id"], d["pdf_page"])})
    related = [{"label": r["label"], "date": r["date"], "gosi_no": r["gosi_no"],
                "source": source(con, r["source_doc_id"], r["pdf_page"])}
               for r in con.execute("SELECT * FROM related_history WHERE project_id=? ORDER BY date", (project_id,))]
    docs = [{"doc_id": r["doc_id"], "short_title": r["short_title"], "published_at": r["published_at"],
             "role": r["role"]}
            for r in con.execute("""SELECT d.doc_id, d.short_title, d.published_at, pd.role FROM project_documents pd
                                    JOIN documents d ON d.id = pd.document_id WHERE pd.project_id=?""", (project_id,))]
    # 고시에 적힌 수치 (Claude Code 추출값 — 근거 문장·원문 쪽과 함께만 보여준다)
    from core.catalog import FIELD_LABELS
    ex = con.execute("SELECT payload FROM extractions WHERE document_id=?", (p["stage_source_doc_id"],)).fetchone()
    units = {k: v.get("unit") for k, v in (loads(ex["payload"], {}) or {}).get("fields", {}).items()} if ex else {}
    frows = {r["field"]: r for r in con.execute("SELECT * FROM extracted_fields WHERE document_id=?",
                                                 (p["stage_source_doc_id"],))}
    facts = [{"field": f, "label": FIELD_LABELS.get(f, f), "value": loads(frows[f]["value"]), "unit": units.get(f),
              "evidence": frows[f]["evidence"], "evidence_ok": bool(frows[f]["evidence_ok"]),
              "source": source(con, p["stage_source_doc_id"], frows[f]["pdf_page"])}
             for f in FACT_FIELDS if f in frows and loads(frows[f]["value"]) is not None]
    h = hist.get(p["sub_stage_code"])
    label = PROJECT_TYPE_LABELS.get(p["project_type"], p["project_type"])
    return {
        "project_id": p["id"],
        "name": p["name"],
        "aliases": loads(p["aliases"], []),
        "project_type": p["project_type"],
        "project_type_label": label,
        "track": p["track"],
        "track_label": TRACK_LABELS.get(p["track"], p["track"]),
        "location_text": p["location_text"],
        "area_m2": p["area_m2"],
        "center": {"lat": p["lat"], "lon": p["lon"], "coord_source": p["coord_source"]} if p["lat"] is not None else None,
        "as_of": p["stage_as_of"] or m.get("as_of"),
        "position_label": f"{label} {len(tpls)}단계 중 {cur['seq']}번째",
        "stages": stages,
        "current": {"code": cur["sub_stage_code"], "title": cur["title"], "what_happens": cur["what_happens"],
                    "what_happens_note": None if cur["what_happens"] else WHAT_HAPPENS_NOTE,
                    "owner_actions": cur["owner_actions"], "issuer": cur["issuer"],
                    "legal_basis": cur["legal_basis"], "template_status": template_status(cur),
                    "template_source": cur["source"]},
        "next": {"code": nxt["sub_stage_code"], "title": nxt["title"], "owner_actions": nxt["owner_actions"]}
        if nxt else None,
        "deadlines": deadlines,
        "remaining": dict(REMAINING),
        "facts": facts,
        "facts_note": "고시 원문에서 추출한 수치입니다. 근거 문장과 원문 쪽을 함께 확인하세요.",
        "related_history": related,
        "documents": docs,
        "stage_basis": {"rule_id": p["stage_rule"], "evidence": h["evidence"] if h else None,
                        "source": source(con, h["source_doc_id"], h["pdf_page"]) if h else None},
        "review_applied": ov.review_applied,
        "events": ov.events,
        "disclaimer": DISCLAIMER,
    }
