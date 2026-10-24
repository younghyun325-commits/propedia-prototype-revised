"""시드 적재: sources, documents, pages, bjd_codes, demo_addresses, stage_templates (agents.md §8-9)."""
import csv
import json

import yaml

from pipeline.common import (DATA_RAW, DOC_ORDER, DOCS, ROOT, SEED, SOURCES, TEXT_DIR, connect_rw, fail, log,
                             ranges_str, setup_stdout)

MIN_CHARS = 30


def read_csv(path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def none_if_blank(v):
    return None if v in ("", None) else v


def text_status(pages: list[dict]) -> str:
    sel = [p for p in pages if p["selected"]]
    if not sel:
        return "failed"
    rate = sum(p["char_count"] >= MIN_CHARS for p in sel) / len(sel)
    return "ok" if rate == 1 else "partial" if rate >= 0.5 else "failed"


def load(con) -> dict:
    for sid, s in SOURCES.items():
        con.execute("INSERT INTO sources(id, name, layer, url) VALUES (?,?,?,?)", (sid, s["name"], s["layer"], s["url"]))

    manifest = {r["doc_id"]: r for r in read_csv(DATA_RAW / "manifest.csv")}
    counts = {}
    for doc in DOC_ORDER:
        d = DOCS[doc]
        m = manifest.get(doc) or fail(f"manifest.csv에 {doc}가 없습니다 (python -m pipeline.collect)")
        pj = TEXT_DIR / doc / "pages.json"
        if not pj.exists():
            fail(f"{pj}가 없습니다 (python -m pipeline.textify)")
        pages = json.loads(pj.read_text(encoding="utf-8"))
        cur = con.execute(
            """INSERT INTO documents(doc_id, source_id, title, short_title, doc_kind, issuer, gosi_no, published_at,
               source_url, source_note, original_path, excerpt_path, page_ranges, content_hash, excerpt_hash,
               ingest_step, text_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (doc, d["source_id"], d["title"], d["short_title"], d["doc_kind"], d["issuer"], d["gosi_no"],
             d["published_at"], d["source_url"], d["source_note"], m["original_path"], m["excerpt_path"],
             ranges_str(d["ranges"]), m["original_sha256"], m["excerpt_sha256"], d["ingest_step"],
             text_status(pages)))
        doc_pk = cur.lastrowid
        for p in pages:
            text = (TEXT_DIR / doc / f"p{p['pdf_page']:03d}.txt").read_text(encoding="utf-8")
            con.execute(
                """INSERT INTO pages(document_id, pdf_page, page_label, method, text, char_count, image_url, selected)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (doc_pk, p["pdf_page"], p["page_label"], p["method"], text, p["char_count"], p["image_url"],
                 p["selected"]))
        counts[doc] = len(pages)

    for r in read_csv(SEED / "bjd_codes.csv"):
        con.execute("INSERT INTO bjd_codes VALUES (?,?,?,?,?,?)",
                    (r["bjd_code"], r["sgg_code"], r["dong_name"], none_if_blank(r["saenghwal"]),
                     int(r["code_verified"]), int(r["saenghwal_verified"])))

    for r in read_csv(SEED / "demo_addresses.csv"):
        con.execute(
            """INSERT INTO demo_addresses(addr_id, label, input_text, road_address, jibun_address, pnu, bjd_code,
               sgg_code, building_name, lat, lon, coord_source, aliases, in_scope) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["addr_id"], r["label"], r["input_text"], none_if_blank(r["road_address"]),
             none_if_blank(r["jibun_address"]), none_if_blank(r["pnu"]), none_if_blank(r["bjd_code"]),
             none_if_blank(r["sgg_code"]), none_if_blank(r["building_name"]),
             float(r["lat"]) if r["lat"] else None, float(r["lon"]) if r["lon"] else None,
             none_if_blank(r["coord_source"]), r["aliases"] or "[]", int(r["in_scope"])))

    tpl = yaml.safe_load((SEED / "stage_templates.yaml").read_text(encoding="utf-8"))
    for s in tpl["stages"]:
        con.execute(
            """INSERT INTO stage_templates(project_type, seq, sub_stage_code, common_stage, title, issuer, what_happens,
               owner_actions, legal_basis, source, reviewed_by, reviewed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tpl["project_type"], s["seq"], s["code"], s.get("common_stage"), s["title"], s.get("issuer"),
             s.get("what_happens"), s.get("owner_actions"), s.get("legal_basis"), tpl["source"],
             tpl.get("reviewed_by"), tpl.get("reviewed_at")))
    return counts


def main() -> None:
    setup_stdout()
    con = connect_rw()
    counts = load(con)
    con.commit()
    n_addr = con.execute("SELECT count(*) FROM demo_addresses").fetchone()[0]
    n_tpl = con.execute("SELECT count(*) FROM stage_templates").fetchone()[0]
    st = dict(con.execute("SELECT doc_id, text_status FROM documents").fetchall())
    con.close()
    log(f"load_seed: 문서 4건 (쪽 {counts}), text_status {st}, 시연 주소 {n_addr}건, 단계 템플릿 {n_tpl}개")


if __name__ == "__main__":
    main()
