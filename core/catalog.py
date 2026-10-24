"""문서 DB·투입 이벤트·검수 목록·평가 조회 (agents.md §11-2 문서/이벤트/검수/평가 엔드포인트)."""
from core.db import loads, meta, source

FIELD_LABELS = {
    "gosi_no": "공고번호", "published_at": "공고일", "gazette_no": "구보 호수", "gazette_date": "구보 발행일",
    "issuer": "공고자", "legal_basis": "근거 법령", "project_name": "정비사업 명칭", "location_text": "정비구역 위치",
    "representative_jibun": "대표 지번", "area_m2": "정비구역 면적", "public_review_start": "공람 시작일",
    "public_review_end": "공람 종료일", "review_places": "공람장소", "land_use": "용도지역",
    "households_before": "현황 세대수", "households_after": "계획 세대수", "base_allowed_far": "기준(허용) 용적률",
    "plan_far": "정비계획 용적률", "legal_max_far": "법정상한 용적률",
}
ITEM_TYPE_LABELS = {"policy": "정책", "plan": "계획", "notice": "고시·공고", "stat": "현황 수치"}
METHOD_LABELS = {"text": "텍스트", "vision-claude": "전사", "image-only": "이미지만"}
REVIEW_TYPE_LABELS = {
    "parcel_inclusion": "포함 판정", "evidence_mismatch": "근거 불일치", "vision_item": "이미지 전사 항목",
    "scope_uncertain": "적용 범위 판단", "field_low_confidence": "낮은 신뢰도 필드", "stage_uncertain": "단계 판정",
}
EVENT_LABELS = {"new_project": "새 사업 카드", "stage_change": "단계 변경", "deadline_added": "기한 추가",
                "doc_attached": "문서 연결"}
DOC_KIND_LABELS = {"gongram": "공람·공고", "plan": "계획"}
MIN_CHARS = 30


def _doc_row(con, doc_id: str):
    return con.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()


def _source_info(con, d) -> dict:
    s = con.execute("SELECT * FROM sources WHERE id=?", (d["source_id"],)).fetchone()
    return {"source_id": d["source_id"], "name": s["name"] if s else None, "source_url": d["source_url"],
            "source_note": d["source_note"]}


def list_documents(con) -> list[dict]:
    out = []
    for d in con.execute("SELECT * FROM documents ORDER BY ingest_step"):
        sel = con.execute("SELECT count(*) FROM pages WHERE document_id=? AND selected=1", (d["id"],)).fetchone()[0]
        ok = con.execute("SELECT count(*) FROM pages WHERE document_id=? AND selected=1 AND char_count>=?",
                         (d["id"], MIN_CHARS)).fetchone()[0]
        items = con.execute("SELECT count(*) FROM applicability_rules WHERE document_id=?", (d["id"],)).fetchone()[0]
        ex = con.execute("SELECT evidence_ok_count, evidence_total FROM extractions WHERE document_id=?",
                         (d["id"],)).fetchone()
        out.append({
            "doc_id": d["doc_id"], "title": d["title"], "short_title": d["short_title"], "doc_kind": d["doc_kind"],
            "doc_kind_label": DOC_KIND_LABELS.get(d["doc_kind"], d["doc_kind"]), "issuer": d["issuer"],
            "gosi_no": d["gosi_no"], "published_at": d["published_at"], "page_ranges": d["page_ranges"],
            "text_status": d["text_status"], "pages_selected": sel, "pages_text_ok": ok, "items": items,
            "evidence_ok": ex["evidence_ok_count"] if ex else 0, "evidence_total": ex["evidence_total"] if ex else 0,
            "evidence_ok_rate": (ex["evidence_ok_count"] / ex["evidence_total"]) if ex and ex["evidence_total"] else None,
            "ingest_step": d["ingest_step"], "source": _source_info(con, d),
        })
    return out


def _items_of(con, doc_pk: int, pdf_page: int | None = None) -> list[dict]:
    sql = "SELECT * FROM applicability_rules WHERE document_id=?"
    args = [doc_pk]
    if pdf_page is not None:
        sql += " AND pdf_page=?"
        args.append(pdf_page)
    out = []
    for a in con.execute(sql + " ORDER BY item_key", args):
        out.append({"item_key": a["item_key"], "item_type": a["item_type"],
                    "item_type_label": ITEM_TYPE_LABELS.get(a["item_type"], a["item_type"]), "title": a["title"],
                    "summary": a["summary"], "scope_type": a["scope_type"], "scope_ref": loads(a["scope_ref"], []),
                    "scope_note": a["scope_note"], "pdf_page": a["pdf_page"], "evidence": a["evidence"],
                    "evidence_ok": bool(a["evidence_ok"]), "confidence": a["confidence"],
                    "needs_review": bool(a["needs_review"]), "source": source(con, doc_pk, a["pdf_page"])})
    return out


def _fields_of(con, doc_pk: int, payload: dict, pdf_page: int | None = None) -> list[dict]:
    pf = (payload or {}).get("fields", {})
    sql = "SELECT * FROM extracted_fields WHERE document_id=?"
    args = [doc_pk]
    if pdf_page is not None:
        sql += " AND pdf_page=?"
        args.append(pdf_page)
    order = list(FIELD_LABELS)
    rows = sorted(con.execute(sql, args).fetchall(),
                  key=lambda r: order.index(r["field"]) if r["field"] in order else 99)
    return [{"field": r["field"], "label": FIELD_LABELS.get(r["field"], r["field"]), "value": loads(r["value"]),
             "unit": pf.get(r["field"], {}).get("unit"), "null_reason": pf.get(r["field"], {}).get("null_reason"),
             "pdf_page": r["pdf_page"], "confidence": r["confidence"], "evidence": r["evidence"],
             "evidence_ok": bool(r["evidence_ok"]),
             "source": source(con, doc_pk, r["pdf_page"]) if r["pdf_page"] else None} for r in rows]


def _project_evidences(payload: dict) -> list[dict]:
    out = []
    for prj in (payload or {}).get("projects", []):
        for name in ("stage_evidence", "representative_jibun", "area_m2", "land_use"):
            x = prj.get(name)
            if x and x.get("evidence"):
                out.append({"what": name, "evidence": x["evidence"], "pdf_page": x.get("pdf_page")})
        for d in prj.get("deadlines", []):
            out.append({"what": "deadline", "evidence": d.get("evidence"), "pdf_page": d.get("pdf_page")})
            if d.get("how_to_submit"):
                out.append({"what": "how_to_submit", "evidence": d["how_to_submit"], "pdf_page": d.get("pdf_page")})
        for h in prj.get("related_history", []):
            out.append({"what": "related_history", "evidence": h.get("evidence"), "pdf_page": h.get("pdf_page")})
    return out


def document_detail(con, doc_id: str) -> dict | None:
    d = _doc_row(con, doc_id)
    if d is None:
        return None
    ex = con.execute("SELECT * FROM extractions WHERE document_id=?", (d["id"],)).fetchone()
    payload = loads(ex["payload"], {}) if ex else {}
    pages = [{"pdf_page": p["pdf_page"], "page_label": p["page_label"], "method": p["method"],
              "method_label": METHOD_LABELS.get(p["method"], p["method"]), "char_count": p["char_count"],
              "image_url": p["image_url"], "selected": bool(p["selected"])}
             for p in con.execute("SELECT * FROM pages WHERE document_id=? ORDER BY pdf_page", (d["id"],))]
    projects = []
    for p in con.execute("""SELECT p.* FROM projects p JOIN project_documents pd ON pd.project_id=p.id
                            WHERE pd.document_id=?""", (d["id"],)):
        t = con.execute("SELECT title FROM stage_templates WHERE project_type=? AND sub_stage_code=?",
                        (p["project_type"], p["sub_stage_code"])).fetchone()
        projects.append({"project_id": p["id"], "name": p["name"], "aliases": loads(p["aliases"], []),
                         "stage": {"code": p["sub_stage_code"], "title": t["title"] if t else None},
                         "stage_rule": p["stage_rule"], "location_text": p["location_text"],
                         "progress_url": f"/api/v1/projects/{p['id']}/progress"})
    meta_cols = ["doc_id", "title", "short_title", "doc_kind", "issuer", "gosi_no", "published_at", "source_url",
                 "source_note", "original_path", "excerpt_path", "page_ranges", "content_hash", "excerpt_hash",
                 "ingest_step", "text_status"]
    return {
        "document": {k: d[k] for k in meta_cols} | {"doc_kind_label": DOC_KIND_LABELS.get(d["doc_kind"], d["doc_kind"]),
                                                    "source": _source_info(con, d)},
        "pages": pages,
        "fields": _fields_of(con, d["id"], payload),
        "items": _items_of(con, d["id"]),
        "projects": projects,
        "extraction": {"extractor_version": ex["extractor_version"], "extracted_at": ex["extracted_at"],
                       "evidence_ok": ex["evidence_ok_count"], "evidence_total": ex["evidence_total"],
                       "payload": payload} if ex else None,
    }


def page_detail(con, doc_id: str, pdf_page: int) -> dict | None:
    d = _doc_row(con, doc_id)
    if d is None:
        return None
    p = con.execute("SELECT * FROM pages WHERE document_id=? AND pdf_page=?", (d["id"], pdf_page)).fetchone()
    if p is None:
        return None
    ex = con.execute("SELECT payload FROM extractions WHERE document_id=?", (d["id"],)).fetchone()
    payload = loads(ex["payload"], {}) if ex else {}
    items = _items_of(con, d["id"], pdf_page)
    fields = _fields_of(con, d["id"], payload, pdf_page)
    proj_ev = [e for e in _project_evidences(payload) if e["pdf_page"] == pdf_page]
    evidences = []
    for e in [i["evidence"] for i in items] + [f["evidence"] for f in fields if f["evidence"]] + \
             [e["evidence"] for e in proj_ev]:
        if e and e not in evidences:
            evidences.append(e)
    return {"doc_id": doc_id, "short_title": d["short_title"], "pdf_page": pdf_page, "page_label": p["page_label"],
            "method": p["method"], "method_label": METHOD_LABELS.get(p["method"], p["method"]),
            "char_count": p["char_count"], "selected": bool(p["selected"]), "image_url": p["image_url"],
            "text": p["text"], "items": items, "fields": fields, "project_evidences": proj_ev,
            "evidences": evidences, "source": source(con, d["id"], pdf_page)}


def list_events(con) -> list[dict]:
    out = []
    names = {p["id"]: p["name"] for p in con.execute("SELECT id, name FROM projects")}
    for d in con.execute("SELECT * FROM documents ORDER BY ingest_step"):
        evs = []
        for e in con.execute("SELECT * FROM change_events WHERE step=? ORDER BY id", (d["ingest_step"],)):
            evs.append({"event_type": e["event_type"], "event_label": EVENT_LABELS.get(e["event_type"], e["event_type"]),
                        "project_id": e["project_id"], "project_name": names.get(e["project_id"]),
                        "before": loads(e["before"]), "after": loads(e["after"]), "created_at": e["created_at"]})
        out.append({"step": d["ingest_step"], "doc_id": d["doc_id"], "short_title": d["short_title"],
                    "published_at": d["published_at"], "events": evs})
    return out


def list_review_queue(con) -> list[dict]:
    rows = con.execute("SELECT * FROM review_queue").fetchall()
    rows = sorted(rows, key=lambda r: (r["item_type"] != "parcel_inclusion", r["id"]))
    out = []
    for r in rows:
        d = con.execute("SELECT doc_id, short_title FROM documents WHERE id=?", (r["document_id"],)).fetchone()
        out.append({"id": r["id"], "item_type": r["item_type"],
                    "item_type_label": REVIEW_TYPE_LABELS.get(r["item_type"], r["item_type"]),
                    "ref_table": r["ref_table"], "ref_key": r["ref_key"], "title": r["title"], "reason": r["reason"],
                    "proposed": loads(r["proposed"], {}),
                    "document": {"doc_id": d["doc_id"], "short_title": d["short_title"]} if d else None,
                    "pdf_page": r["pdf_page"],
                    "source": source(con, r["document_id"], r["pdf_page"]) if r["document_id"] else None})
    return out


def eval_report(con) -> dict:
    rep = loads(meta(con).get("eval_report"))
    if not rep:
        return {"status": "not_run", "message": "평가 전입니다. python -m evals.run_eval 을 실행하면 결과가 표시됩니다."}
    return rep


def demo_addresses(con) -> list[dict]:
    return [{"addr_id": r["addr_id"], "label": r["label"], "input_text": r["input_text"],
             "road_address": r["road_address"], "jibun_address": r["jibun_address"], "in_scope": bool(r["in_scope"]),
             "available": bool(r["input_text"])}
            for r in con.execute("SELECT * FROM demo_addresses ORDER BY CAST(substr(addr_id, 2) AS INTEGER)")]
