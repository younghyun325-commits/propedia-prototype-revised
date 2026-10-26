"""추출 결과(extractions/Dn.json) 적재 + 근거 문장 자동 검사 (agents.md §8-10, §9, feedback.md §3-4).

사용:
  python -m pipeline.load_extractions          # 적재
  python -m pipeline.load_extractions --check  # 적재 후 문서별 항목 수·근거 일치율·검수 필요 수 출력
"""
import argparse
import json
import re
from datetime import date

from core.text import evidence_in
from pipeline.common import DOC_ORDER, EXTRACTIONS, connect_rw, fail, log, setup_stdout

ITEM_TYPES = {"policy", "plan", "notice", "stat"}
SCOPE_TYPES = {"SIDO", "SGG", "SAENGHWAL", "BJD", "PARCEL"}
ITEM_REQUIRED = ["item_key", "item_type", "title", "summary", "scope_type", "scope_ref", "pdf_page", "evidence",
                 "confidence", "needs_review",
                 # P9: 효력·대상, 층 분류 (claude-code-v1.1)
                 "effective_from", "effective_to", "target_note", "tier", "tier_class", "applies_rank",
                 "reference_rank", "tier_reason"]
TIERS = {"applies", "background"}
TIER_CLASSES = {"a", "b", "c", None}
FIELD_REQUIRED = ["value", "evidence", "pdf_page", "confidence"]
TOP_REQUIRED = ["doc_id", "extractor_version", "extracted_at", "document", "fields", "items", "projects"]
SUMMARY_MAX = 120


def validate(doc: str, data: dict, pages: dict[int, dict]) -> list[str]:
    errs = []
    for k in TOP_REQUIRED:
        if k not in data:
            errs.append(f"최상위 키 없음: {k}")
    if errs:
        return errs
    if data["doc_id"] != doc:
        errs.append(f"doc_id 불일치: {data['doc_id']}")
    seen = set()
    for it in data["items"]:
        key = it.get("item_key", "?")
        for k in ITEM_REQUIRED:
            if k not in it:
                errs.append(f"{key}: 키 없음 {k}")
        if not re.fullmatch(rf"{doc}-\d\d", key):
            errs.append(f"{key}: item_key 형식은 {doc}-NN")
        if key in seen:
            errs.append(f"{key}: item_key 중복")
        seen.add(key)
        if it.get("item_type") not in ITEM_TYPES:
            errs.append(f"{key}: item_type {it.get('item_type')}")
        if it.get("scope_type") not in SCOPE_TYPES:
            errs.append(f"{key}: scope_type {it.get('scope_type')}")
        if not isinstance(it.get("scope_ref"), list) or not it.get("scope_ref"):
            errs.append(f"{key}: scope_ref는 비어 있지 않은 배열")
        p = pages.get(it.get("pdf_page"))
        if not p:
            errs.append(f"{key}: pdf_page {it.get('pdf_page')}는 문서 쪽 범위 밖")
        elif not p["selected"]:
            errs.append(f"{key}: pdf_page {it.get('pdf_page')}는 추출 대상(selected) 쪽이 아님")
        if len(it.get("summary", "")) > SUMMARY_MAX:
            errs.append(f"{key}: summary {len(it['summary'])}자 > {SUMMARY_MAX}자")
        if it.get("tier") not in TIERS:
            errs.append(f"{key}: tier {it.get('tier')}")
        if it.get("tier_class") not in TIER_CLASSES:
            errs.append(f"{key}: tier_class {it.get('tier_class')}")
        if it.get("tier") == "applies" and not it.get("tier_class"):
            errs.append(f"{key}: applies 항목은 tier_class 필요")
        if not it.get("tier_reason"):
            errs.append(f"{key}: tier_reason 필요")
        for k in ("applies_rank", "reference_rank"):
            if it.get(k) is not None and not isinstance(it[k], int):
                errs.append(f"{key}: {k}는 정수 또는 null")
        for k in ("effective_from", "effective_to"):
            v = it.get(k)
            if v is not None:
                try:
                    date.fromisoformat(v)
                except (TypeError, ValueError):
                    errs.append(f"{key}: {k} 날짜 형식 YYYY-MM-DD")
        if it.get("effective_from") and it.get("effective_to") and it["effective_from"] > it["effective_to"]:
            errs.append(f"{key}: effective_from > effective_to")
        for m in it.get("more_evidence", []):
            if not m.get("label") or not m.get("evidence") or m.get("pdf_page") not in pages:
                errs.append(f"{key}: more_evidence는 label·evidence·문서 쪽 범위 안 pdf_page 필요")
    for name, f in data["fields"].items():
        for k in FIELD_REQUIRED:
            if k not in f:
                errs.append(f"field {name}: 키 없음 {k}")
        if f.get("value") is None and not f.get("null_reason"):
            errs.append(f"field {name}: 값이 null이면 null_reason 필요")
    if doc != "D1" and (data["fields"] or data["projects"]):
        errs.append("fields·projects는 D1에만 둔다")
    return errs


def project_evidences(prj: dict) -> list[tuple[str, str, int]]:
    """사업 JSON 안의 (이름, 근거, 쪽) 목록."""
    out = []
    key = prj.get("project_key", "?")
    for name in ("stage_evidence", "representative_jibun", "area_m2", "land_use"):
        x = prj.get(name)
        if x and x.get("evidence"):
            out.append((f"{key}:{name}", x["evidence"], x.get("pdf_page")))
    for i, d in enumerate(prj.get("deadlines", [])):
        out.append((f"{key}:deadline{i + 1}", d.get("evidence"), d.get("pdf_page")))
        if d.get("how_to_submit"):   # 제출 방법은 원문 문구 그대로여야 한다
            out.append((f"{key}:deadline{i + 1}:how_to_submit", d["how_to_submit"], d.get("pdf_page")))
    for i, h in enumerate(prj.get("related_history", [])):
        out.append((f"{key}:history{i + 1}", h.get("evidence"), h.get("pdf_page")))
    return out


def load(con, only: list[str] | None = None) -> list[dict]:
    stats = []
    for doc in DOC_ORDER:
        if only and doc not in only:
            continue
        path = EXTRACTIONS / f"{doc}.json"
        if not path.exists():
            stats.append({"doc": doc, "missing": True})
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        doc_pk = con.execute("SELECT id FROM documents WHERE doc_id=?", (doc,)).fetchone()[0]
        pages = {r["pdf_page"]: dict(r) for r in
                 con.execute("SELECT pdf_page, text, selected FROM pages WHERE document_id=?", (doc_pk,))}
        errs = validate(doc, data, pages)
        if errs:
            fail(f"{path.name} 스키마 오류 {len(errs)}건:\n  " + "\n  ".join(errs[:30]))

        def ev_ok(ev, pg) -> bool:
            return bool(ev) and pg in pages and evidence_in(ev, pages[pg]["text"])

        con.execute("DELETE FROM applicability_rules WHERE document_id=?", (doc_pk,))
        con.execute("DELETE FROM extracted_fields WHERE document_id=?", (doc_pk,))
        con.execute("DELETE FROM extractions WHERE document_id=?", (doc_pk,))
        con.execute("DELETE FROM review_queue WHERE document_id=? AND item_type='evidence_mismatch'", (doc_pk,))

        mism = []
        ok_n = total = 0
        for it in data["items"]:
            ok = ev_ok(it["evidence"], it["pdf_page"])
            ok_n += ok
            total += 1
            more = []
            for m in it.get("more_evidence", []):   # 기간·면적·도면 근거도 같은 규칙으로 검사한다
                m_ok = ev_ok(m["evidence"], m["pdf_page"])
                ok_n += m_ok
                total += 1
                more.append({**m, "evidence_ok": m_ok})
                if not m_ok:
                    mism.append(("applicability_rules", it["item_key"], f"{it['title']} ({m['label']})",
                                 m["evidence"], m["pdf_page"]))
            con.execute(
                """INSERT INTO applicability_rules(item_key, document_id, item_type, title, summary, scope_type,
                   scope_ref, scope_note, pdf_page, evidence, evidence_ok, effective_from, confidence, needs_review,
                   effective_to, target_note, more_evidence, tier, tier_class, applies_rank, reference_rank,
                   tier_reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (it["item_key"], doc_pk, it["item_type"], it["title"], it["summary"], it["scope_type"],
                 json.dumps(it["scope_ref"], ensure_ascii=False), it.get("scope_note"), it["pdf_page"],
                 it["evidence"], int(ok and all(m["evidence_ok"] for m in more)), it.get("effective_from"),
                 float(it["confidence"]), int(bool(it["needs_review"])), it.get("effective_to"),
                 it.get("target_note"), json.dumps(more, ensure_ascii=False), it["tier"], it.get("tier_class"),
                 it.get("applies_rank"), it.get("reference_rank"), it["tier_reason"]))
            if not ok:
                mism.append(("applicability_rules", it["item_key"], it["title"], it["evidence"], it["pdf_page"]))
        for name, f in data["fields"].items():
            has_ev = bool(f.get("evidence"))
            ok = ev_ok(f.get("evidence"), f.get("pdf_page")) if has_ev else False
            if has_ev:
                ok_n += ok
                total += 1
                if not ok:
                    mism.append(("extracted_fields", f"{doc}:{name}", f"필드 {name}", f["evidence"], f["pdf_page"]))
            con.execute(
                """INSERT INTO extracted_fields(document_id, field, value, evidence, pdf_page, confidence, evidence_ok)
                   VALUES (?,?,?,?,?,?,?)""",
                (doc_pk, name, json.dumps(f.get("value"), ensure_ascii=False), f.get("evidence"), f.get("pdf_page"),
                 float(f["confidence"]), int(ok)))
        for prj in data["projects"]:
            for name, ev, pg in project_evidences(prj):
                ok = ev_ok(ev, pg)
                ok_n += ok
                total += 1
                if not ok:
                    mism.append(("projects", f"{doc}:{name}", f"사업 {name}", ev, pg))
        for table, ref, title, ev, pg in mism:
            con.execute(
                """INSERT INTO review_queue(item_type, ref_table, ref_key, title, reason, proposed, document_id, pdf_page)
                   VALUES ('evidence_mismatch',?,?,?,?,?,?,?)""",
                (table, ref, f"{title} — 근거 확인 필요", "근거 문장이 쪽 텍스트에서 그대로 찾아지지 않음",
                 json.dumps({"current": {"evidence": ev, "pdf_page": pg}, "options": ["approve", "reject", "edit"],
                             "editable_fields": ["summary", "scope_type", "scope_ref", "tier"]
                             if table == "applicability_rules" else []}, ensure_ascii=False),
                 doc_pk, pg))
        con.execute(
            """INSERT INTO extractions(document_id, extractor_version, extracted_at, payload, evidence_ok_count,
               evidence_total) VALUES (?,?,?,?,?,?)""",
            (doc_pk, data["extractor_version"], data["extracted_at"], json.dumps(data, ensure_ascii=False), ok_n,
             total))
        stats.append({"doc": doc, "items": len(data["items"]), "fields": len(data["fields"]),
                      "projects": len(data["projects"]), "ok": ok_n, "total": total,
                      "review": sum(bool(i["needs_review"]) for i in data["items"]), "mism": mism})
    return stats


def main() -> None:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("docs", nargs="*")
    args = ap.parse_args()
    con = connect_rw()
    stats = load(con, args.docs or None)
    con.commit()
    con.close()
    log("문서 | 항목 | 필드 | 사업 | 근거 일치 | 일치율 | needs_review")
    for s in stats:
        if s.get("missing"):
            log(f"{s['doc']} | (추출 파일 없음)")
            continue
        rate = s["ok"] / s["total"] if s["total"] else 0
        log(f"{s['doc']} | {s['items']} | {s['fields']} | {s['projects']} | {s['ok']}/{s['total']} | {rate:.1%} | {s['review']}")
    if args.check:
        for s in stats:
            for table, ref, title, ev, pg in s.get("mism", []):
                log(f"  불일치 {s['doc']} p{pg} {ref}: {str(ev)[:40]}")


if __name__ == "__main__":
    main()
