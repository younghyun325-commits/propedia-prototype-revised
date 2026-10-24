"""검수 큐 보충 (agents.md §8-13). 앞 단계가 넣은 것(evidence_mismatch, parcel_inclusion, stage_uncertain) 외에:

- applicability_rules.needs_review=1 → 전사 쪽이면 vision_item, 아니면 scope_uncertain
- applicability_rules.confidence < 0.7 → scope_uncertain
- extracted_fields.confidence < 0.8 → field_low_confidence
- (item_type, ref_key) 중복 방지
"""
import json

from pipeline.common import connect_rw, log, setup_stdout

ITEM_EDITABLE = ["summary", "scope_type", "scope_ref"]


def build(con) -> dict[str, int]:
    con.execute("DELETE FROM review_queue WHERE item_type IN ('vision_item','scope_uncertain','field_low_confidence')")
    existing = {(r["item_type"], r["ref_key"]) for r in con.execute("SELECT item_type, ref_key FROM review_queue")}

    def add(item_type, ref_table, ref_key, title, reason, proposed, doc_pk, page):
        if (item_type, ref_key) in existing:
            return
        existing.add((item_type, ref_key))
        con.execute(
            """INSERT INTO review_queue(item_type, ref_table, ref_key, title, reason, proposed, document_id, pdf_page)
               VALUES (?,?,?,?,?,?,?,?)""",
            (item_type, ref_table, ref_key, title, reason, json.dumps(proposed, ensure_ascii=False), doc_pk, page))

    rows = con.execute(
        """SELECT a.*, p.method FROM applicability_rules a
           JOIN pages p ON p.document_id = a.document_id AND p.pdf_page = a.pdf_page ORDER BY a.item_key""").fetchall()
    for a in rows:
        current = {"item_key": a["item_key"], "title": a["title"], "summary": a["summary"],
                   "scope_type": a["scope_type"], "scope_ref": json.loads(a["scope_ref"]), "scope_note": a["scope_note"],
                   "evidence": a["evidence"], "pdf_page": a["pdf_page"], "confidence": a["confidence"]}
        proposed = {"current": current, "options": ["approve", "reject", "edit"], "editable_fields": ITEM_EDITABLE}
        if a["confidence"] < 0.7:
            add("scope_uncertain", "applicability_rules", a["item_key"], f"{a['item_key']} {a['title']}",
                f"적용 범위 판단 신뢰도 {a['confidence']:.2f} (0.7 미만)", proposed, a["document_id"], a["pdf_page"])
        elif a["needs_review"]:
            if a["method"] == "vision-claude":
                add("vision_item", "applicability_rules", a["item_key"], f"{a['item_key']} {a['title']}",
                    "이미지 쪽을 Claude Code가 전사한 텍스트에서 나온 항목", proposed, a["document_id"], a["pdf_page"])
            else:
                add("scope_uncertain", "applicability_rules", a["item_key"], f"{a['item_key']} {a['title']}",
                    "검수 필요로 표시된 항목 (2030 생활권계획(2018) 기준 — 적용 범위 확인)", proposed,
                    a["document_id"], a["pdf_page"])
    for f in con.execute(
            """SELECT f.*, d.doc_id FROM extracted_fields f JOIN documents d ON d.id=f.document_id
               WHERE f.confidence < 0.8 ORDER BY f.field"""):
        add("field_low_confidence", "extracted_fields", f"{f['doc_id']}:{f['field']}", f"{f['doc_id']} 필드 {f['field']}",
            f"추출 신뢰도 {f['confidence']:.2f} (0.8 미만)",
            {"current": {"field": f["field"], "value": json.loads(f["value"]) if f["value"] else None,
                         "evidence": f["evidence"], "pdf_page": f["pdf_page"]},
             "options": ["approve", "reject"], "editable_fields": []}, f["document_id"], f["pdf_page"])
    return dict(con.execute("SELECT item_type, count(*) FROM review_queue GROUP BY item_type").fetchall())


def main() -> None:
    setup_stdout()
    con = connect_rw()
    counts = build(con)
    con.commit()
    con.close()
    log(f"review_queue: {counts}")


if __name__ == "__main__":
    main()
