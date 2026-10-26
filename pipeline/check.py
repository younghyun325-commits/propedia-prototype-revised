"""단계 완료 조건 자동 점검 (agents.md §8-15, §18).

사용: python -m pipeline.check P1|P2|P3
통과하지 못한 항목이 있으면 종료 코드 1.
"""
import csv
import json
import sys

import yaml

from pipeline.common import (DATA_RAW, DB_PATH, DOC_ORDER, EXTRACTIONS, ROOT, SEED, TEXT_DIR, connect_rw, log,
                             setup_stdout)

MIN_CHARS = 30


class Checker:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, bool(ok), detail))

    def report(self) -> int:
        w = max(len(n) for n, _, _ in self.rows)
        for name, ok, detail in self.rows:
            log(f"{'통과' if ok else '실패'} | {name.ljust(w)} | {detail}")
        bad = sum(1 for _, ok, _ in self.rows if not ok)
        log(f"→ {len(self.rows) - bad}/{len(self.rows)} 통과")
        return 1 if bad else 0


def human_todo_has(text: str) -> bool:
    p = ROOT / "HUMAN_TODO.md"
    return p.exists() and text in p.read_text(encoding="utf-8")


def load_pages(doc: str) -> list[dict]:
    p = TEXT_DIR / doc / "pages.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def check_p1(c: Checker) -> None:
    man = DATA_RAW / "manifest.csv"
    n = 0
    if man.exists():
        with open(man, encoding="utf-8-sig", newline="") as f:
            n = len(list(csv.DictReader(f)))
    c.add(f"manifest {len(DOC_ORDER)}행", n == len(DOC_ORDER), f"{n}행")
    for d in DOC_ORDER:
        c.add(f"{d} 발췌본", (DATA_RAW / f"{d}.pdf").exists())

    sel = ok = 0
    for d in DOC_ORDER:
        for r in load_pages(d):
            if r["selected"]:
                sel += 1
                ok += r["char_count"] >= MIN_CHARS
    rate = ok / sel if sel else 0
    c.add("선택 쪽 텍스트 확보율 ≥ 95%", rate >= 0.95, f"{ok}/{sel} = {rate:.1%}")

    d2 = load_pages("D2")
    chap = [r for r in d2 if 113 <= r["pdf_page"] <= 151 and r["selected"]]
    chap_ok = all(r["method"] == "vision-claude" for r in chap)
    c.add("D2 113~151 선택 10~15쪽, 전사 완료", 10 <= len(chap) <= 15 and chap_ok,
          f"{len(chap)}쪽, 전사 {sum(r['method'] == 'vision-claude' for r in chap)}")
    ov = [r for r in d2 if 29 <= r["pdf_page"] <= 31 and r["selected"]]
    c.add("D2 29~31 내용 있는 쪽 전사 완료", bool(ov) and all(r["method"] == "vision-claude" for r in ov),
          f"선택 {[r['pdf_page'] for r in ov]} (p29 표지·p30 빈 쪽 제외)")
    sel_yaml = SEED / "d2_selected_pages.yaml"
    c.add("seed/d2_selected_pages.yaml", sel_yaml.exists())

    addr = []
    p = SEED / "demo_addresses.csv"
    if p.exists():
        with open(p, encoding="utf-8-sig", newline="") as f:
            addr = list(csv.DictReader(f))
    c.add("demo_addresses 10행", len(addr) == 10, f"{len(addr)}행")
    pending = [a["addr_id"] for a in addr if a["in_scope"] == "1" and not a["input_text"]]
    missing = [a["addr_id"] for a in addr if a["in_scope"] == "1" and a["input_text"] and not a["pnu"]]
    pending_ok = not pending or human_todo_has("승인키")
    c.add("in_scope 주소는 PNU 있음", not missing and pending_ok,
          f"PNU 없음 {missing or '-'}; 키 재발급 대기 {pending or '-'}" + (" (HUMAN_TODO 기록됨)" if pending else ""))

    bjd = {}
    with open(SEED / "bjd_codes.csv", encoding="utf-8-sig", newline="") as f:
        bjd = {r["dong_name"]: r for r in csv.DictReader(f)}
    ap = bjd.get("압구정동", {})
    ok_code = ap.get("code_verified") == "1" or human_todo_has("승인키")
    c.add("압구정동 코드 확인 (API 실패 시 0 + HUMAN_TODO)", ok_code,
          f"code_verified={ap.get('code_verified')}")
    c.add("생활권 확정 (압구정동·청담동·신사동)",
          all(bjd.get(d, {}).get("saenghwal") == "압구정·청담" and bjd[d]["saenghwal_verified"] == "1"
              for d in ("압구정동", "청담동", "신사동")))

    for name in ("extraction.yaml", "addresses.yaml"):
        g = ROOT / "evals" / "goldset" / name
        draft = g.exists() and (yaml.safe_load(g.read_text(encoding="utf-8")) or {}).get("draft") is True
        c.add(f"정답셋 초안 {name}", draft)


def check_p2(c: Checker) -> None:
    from pipeline.load_extractions import validate
    if not DB_PATH.exists():
        c.add("DB 존재", False, "python -m pipeline.init_db && python -m pipeline.load_seed")
        return
    con = connect_rw()
    min_items = {"D1": 2, "D2": 8, "D3": 5, "D4": 5, "D5": 1, "D6": 1, "D7": 1, "D8": 1}   # D5~D8: feedback.md §2-2-3
    all_keys = set()
    for doc in DOC_ORDER:
        p = EXTRACTIONS / f"{doc}.json"
        if not p.exists():
            c.add(f"{doc} 추출 JSON", False, "파일 없음")
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        doc_pk = con.execute("SELECT id FROM documents WHERE doc_id=?", (doc,)).fetchone()[0]
        pages = {r["pdf_page"]: dict(r) for r in
                 con.execute("SELECT pdf_page, text, selected FROM pages WHERE document_id=?", (doc_pk,))}
        errs = validate(doc, data, pages)
        c.add(f"{doc} 스키마", not errs, "; ".join(errs[:3]))
        n = len(data["items"])
        c.add(f"{doc} 항목 수 ≥ {min_items[doc]}", n >= min_items[doc], f"{n}개")
        all_keys |= {i["item_key"] for i in data["items"]}
        if doc == "D1":
            c.add("D1 필드 19개", len(data["fields"]) == 19, f"{len(data['fields'])}개")
            c.add("D1 사업 1건", len(data["projects"]) == 1, f"{len(data['projects'])}건")
        if doc == "D2":
            c.add("D2 항목 전부 needs_review", all(i["needs_review"] for i in data["items"]))
    row = con.execute("SELECT sum(evidence_ok_count), sum(evidence_total) FROM extractions").fetchone()
    ok, total = row[0] or 0, row[1] or 0
    mism = con.execute("SELECT count(*) FROM review_queue WHERE item_type='evidence_mismatch'").fetchone()[0]
    c.add("근거 일치율 100% (불일치는 전부 검수 큐)", total > 0 and (ok == total or mism == total - ok),
          f"{ok}/{total}, 검수 큐 {mism}")
    con.close()
    g = ROOT / "evals" / "goldset" / "scope_labels.yaml"
    labels = (yaml.safe_load(g.read_text(encoding="utf-8")) or {}) if g.exists() else {}
    missing = sorted(all_keys - set((labels.get("labels") or {}).keys()))
    c.add("정답셋 초안 scope_labels.yaml (모든 item_key)", labels.get("draft") is True and not missing,
          f"누락 {missing[:5]}" if missing else f"{len(all_keys)}개")


def check_p3(c: Checker) -> None:
    from pipeline.run_all import P3_SQL, sql_rows
    if not DB_PATH.exists():
        c.add("DB 존재", False, "python -m pipeline.run_all")
        return
    con = connect_rw()
    for sql, expect in P3_SQL:
        got = sql_rows(con, sql)
        c.add(sql[:60], got == expect, got)
    for t in ("stage_templates", "project_stage_history", "related_history", "review_queue"):
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        c.add(f"{t} 행 있음", n > 0, f"{n}행")
    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    c.add("meta(build_at, as_of, coverage_note)", all(k in meta for k in ("build_at", "as_of", "coverage_note")),
          f"as_of={meta.get('as_of')}")
    con.close()


def main() -> None:
    setup_stdout()
    if len(sys.argv) != 2 or sys.argv[1] not in CHECKS:
        log("사용: python -m pipeline.check P1|P2|P3")
        sys.exit(2)
    c = Checker()
    CHECKS[sys.argv[1]](c)
    sys.exit(c.report())


CHECKS = {"P1": check_p1, "P2": check_p2, "P3": check_p3}

if __name__ == "__main__":
    main()
