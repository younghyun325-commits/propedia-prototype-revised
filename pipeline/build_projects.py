"""사업 카드·단계·기한·포함 판정 (agents.md §8-11).

- 단계는 seed/stage_rules.yaml 을 문서 제목(공백만 정리)에 적용해 정한다. 추출값(stage_candidate)과 다르면 검수 큐.
- 대표 지번만 있는 필지는 basis='representative_only', verified=0 → 검수 큐(parcel_inclusion).
"""
import csv
import json
import re

import yaml

from core.address import make_pnu
from core.text import squash_ws
from pipeline.common import EXTRACTIONS, SEED, connect_rw, fail, log, setup_stdout


def load_rules() -> list[dict]:
    return yaml.safe_load((SEED / "stage_rules.yaml").read_text(encoding="utf-8"))


def judge_stage(title: str, project_type: str, rules: list[dict]) -> tuple[str, str] | None:
    t = squash_ws(title)
    for r in rules:
        if r["project_type"] == project_type and re.search(r["pattern"], t):
            return r["code"], r["id"]
    return None


def project_center(con, project_key: str, anchors: dict) -> tuple:
    """사업 중심점: A1 좌표 → A2 좌표 → seed/project_coords.csv의 인접 필지 근사 (§8-8-4)."""
    for aid in ("A1", "A2"):
        r = con.execute("SELECT lat, lon, coord_source FROM demo_addresses WHERE addr_id=?", (aid,)).fetchone()
        if r and r["lat"] is not None:
            return r["lat"], r["lon"], f"{aid} {r['coord_source']}"
    a = anchors.get(project_key)
    if a:
        return float(a["lat"]), float(a["lon"]), a["note"]
    return None, None, None


def review(con, item_type, ref_table, ref_key, title, reason, proposed, doc_pk, page) -> None:
    con.execute(
        """INSERT INTO review_queue(item_type, ref_table, ref_key, title, reason, proposed, document_id, pdf_page)
           VALUES (?,?,?,?,?,?,?,?)""",
        (item_type, ref_table, ref_key, title, reason, json.dumps(proposed, ensure_ascii=False), doc_pk, page))


def build(con) -> list[dict]:
    rules = load_rules()
    out = []
    data = json.loads((EXTRACTIONS / "D1.json").read_text(encoding="utf-8"))
    doc = con.execute("SELECT id, title, published_at FROM documents WHERE doc_id='D1'").fetchone()
    doc_pk = doc["id"]
    bjd = {r["dong_name"]: dict(r) for r in con.execute("SELECT * FROM bjd_codes")}
    anchors = {}
    if (SEED / "project_coords.csv").exists():
        with open(SEED / "project_coords.csv", encoding="utf-8-sig", newline="") as f:
            anchors = {r["project_key"]: r for r in csv.DictReader(f) if r["lat"]}

    for prj in data["projects"]:
        judged = judge_stage(doc["title"], prj["project_type"], rules)
        if not judged:
            fail(f"{prj['project_key']}: 문서 제목에 맞는 단계 규칙이 없습니다. stage_rules.yaml 확인")
        code, rule_id = judged
        rj = prj["representative_jibun"]
        dong = bjd.get(rj["dong"]) or fail(f"법정동 코드표에 {rj['dong']}가 없습니다")
        pnu = make_pnu(dong["bjd_code"], rj["main"], rj.get("sub", 0), rj.get("san", False))
        lat, lon, csrc = project_center(con, prj["project_key"], anchors)
        has_coord = lat is not None
        cur = con.execute(
            """INSERT INTO projects(project_key, name, aliases, project_type, track, sgg_code, bjd_code, sub_stage_code,
               stage_as_of, stage_source_doc_id, stage_rule, area_m2, location_text, land_use, land_use_page,
               lat, lon, coord_source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (prj["project_key"], prj["name"], json.dumps(prj.get("aliases", []), ensure_ascii=False),
             prj["project_type"], "unknown", dong["sgg_code"], dong["bjd_code"], code, doc["published_at"], doc_pk,
             rule_id, prj["area_m2"]["value"], prj.get("location_text"), prj["land_use"]["value"],
             prj["land_use"]["pdf_page"], lat, lon, csrc))
        pid = cur.lastrowid
        if prj.get("stage_candidate") and prj["stage_candidate"] != code:
            review(con, "stage_uncertain", "projects", str(pid), f"{prj['name']} — 단계 판정",
                   f"추출 후보 {prj['stage_candidate']}와 규칙 {rule_id} 결과 {code}가 다름 (규칙 결과를 씀)",
                   {"current": {"rule": rule_id, "code": code, "candidate": prj["stage_candidate"]},
                    "options": ["approve", "reject"], "editable_fields": []}, doc_pk, prj["stage_evidence"]["pdf_page"])

        se = prj["stage_evidence"]
        con.execute(
            """INSERT INTO project_stage_history(project_id, sub_stage_code, entered_at, source_doc_id, basis, pdf_page,
               evidence) VALUES (?,?,?,?,?,?,?)""", (pid, code, doc["published_at"], doc_pk, "gosi", se["pdf_page"],
                                                    se["evidence"]))
        for h in prj.get("related_history", []):
            con.execute(
                """INSERT INTO related_history(project_id, label, date, gosi_no, source_doc_id, pdf_page, evidence)
                   VALUES (?,?,?,?,?,?,?)""", (pid, h["label"], h.get("date"), h.get("gosi_no"), doc_pk,
                                               h["pdf_page"], h["evidence"]))
        for d in prj.get("deadlines", []):
            con.execute(
                """INSERT INTO deadlines(project_id, kind, title, starts_on, due_on, how_to_submit, places,
                   source_doc_id, pdf_page, evidence) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (pid, d["kind"], d["title"], d.get("starts_on"), d["due_on"], d.get("how_to_submit"),
                 json.dumps(d.get("places", []), ensure_ascii=False), doc_pk, d["pdf_page"], d["evidence"]))
        con.execute(
            """INSERT INTO doc_locations(document_id, pnu, bjd_code, sgg_code, method, jibun_text, pdf_page, evidence,
               confidence) VALUES (?,?,?,?,?,?,?,?,?)""",
            (doc_pk, pnu, dong["bjd_code"], dong["sgg_code"], "representative", rj["text"], rj["pdf_page"],
             rj["evidence"], 0.6))
        con.execute(
            """INSERT INTO project_parcels(project_id, pnu, basis, verified, source_doc_id, pdf_page, evidence)
               VALUES (?,?,?,?,?,?,?)""", (pid, pnu, "representative_only", 0, doc_pk, rj["pdf_page"], rj["evidence"]))
        short = (prj.get("aliases") or [prj["name"]])[0]
        review(con, "parcel_inclusion", "project_parcels", f"{pid}:{pnu}",
               f"{short} — {rj['dong']} {rj['main']} 포함 여부",
               f"고시에 지번 조서 없이 대표 지번(\"{rj['text']}\")만 있음",
               {"current": {"project": prj["name"], "pnu": pnu, "jibun": f"{rj['dong']} {rj['main']}",
                            "inclusion": "possible", "basis": "representative_only",
                            "evidence": rj["evidence"], "pdf_page": rj["pdf_page"]},
                "options": ["approve", "reject"], "editable_fields": []}, doc_pk, rj["pdf_page"])
        con.execute("INSERT INTO project_documents(project_id, document_id, role) VALUES (?,?,?)",
                    (pid, doc_pk, "stage_basis"))
        out.append({"project_id": pid, "key": prj["project_key"], "stage": code, "rule": rule_id, "pnu": pnu,
                    "coord": has_coord})
    return out


def main() -> None:
    setup_stdout()
    con = connect_rw()
    con.execute("DELETE FROM review_queue WHERE item_type IN ('parcel_inclusion','stage_uncertain')")
    for t in ("project_documents", "project_parcels", "doc_locations", "deadlines", "related_history",
              "project_stage_history", "projects"):
        con.execute(f"DELETE FROM {t}")
    res = build(con)
    con.commit()
    con.close()
    for r in res:
        log(f"build_projects: {r['key']} 단계 {r['stage']}({r['rule']}) 대표 필지 {r['pnu']} "
            f"좌표 {'있음' if r['coord'] else '없음(500m 판정 생략)'}")


if __name__ == "__main__":
    main()
