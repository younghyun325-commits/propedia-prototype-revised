"""사업 카드·단계·기한·포함 판정 (agents.md §8-11, feedback2.md §5-3·§5-4).

- 사업은 추출 JSON의 projects에서 만든다 (D1 재건축 한양7차, D9 모아타운 대청마을 북측).
- 단계는 seed/stage_rules.yaml 을 문서 제목(공백만 정리)에 적용해 정한다. 추출값(stage_candidate)과 다르면 검수 큐.
- 대표 지번만 있는 필지는 basis='representative_only', verified=0 → 검수 큐(parcel_inclusion).
- 지도 대조 후보(seed/daecheong_map_reading.csv)는 basis='map_reading', verified=0 → 사업마다 검수 1건(parcel_group).
- 그 밖의 사업의 결정도 대조 필지(seed/map_reading_parcels.csv, P13.5: 한양7차 528)도 basis='map_reading', verified=0.
  이 묶음 검수(parcel_group)는 기존 검수 id가 밀리지 않게 review_queue.py 맨 끝에서 넣는다 (extra_group_reviews).
  pipeline/patch_parcels.py가 같은 함수로 DB만 갱신한다.
- 사업 중심 좌표: seed/project_coords.csv(대표 지번을 브이월드 지오코더로 받은 값) → 같은 PNU 시연 주소 좌표.
"""
import csv
import json
import re

import yaml

from core.address import make_pnu
from core.catalog import FIELD_LABELS
from core.text import evidence_in, squash_ws
from pipeline.common import DOC_ORDER, EXTRACTIONS, SEED, connect_rw, fail, log, setup_stdout

D1_FACT_FIELDS = ["area_m2", "land_use", "households_before", "households_after", "base_allowed_far", "plan_far",
                  "legal_max_far"]
MAP_READING_CSV = SEED / "daecheong_map_reading.csv"
MAP_READING_PROJECT = "ilwon-daecheong-north-moatown"
EXTRA_MAP_CSV = SEED / "map_reading_parcels.csv"


def load_rules() -> list[dict]:
    return yaml.safe_load((SEED / "stage_rules.yaml").read_text(encoding="utf-8"))


def judge_stage(title: str, project_type: str, rules: list[dict]) -> dict | None:
    t = squash_ws(title)
    for r in rules:
        if r["project_type"] == project_type and re.search(r["pattern"], t):
            return r
    return None


def read_csv(path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def project_center(con, project_key: str, pnu: str, anchors: dict) -> tuple:
    a = anchors.get(project_key)
    if a and a.get("lat"):
        return float(a["lat"]), float(a["lon"]), a["coord_source"]
    r = con.execute("SELECT addr_id, lat, lon, coord_source FROM demo_addresses WHERE pnu=? AND lat IS NOT NULL "
                    "ORDER BY addr_id", (pnu,)).fetchone()
    if r:
        return r["lat"], r["lon"], f"{r['addr_id']} {r['coord_source']}"
    return None, None, None


def review(con, item_type, ref_table, ref_key, title, reason, proposed, doc_pk, page) -> None:
    con.execute(
        """INSERT INTO review_queue(item_type, ref_table, ref_key, title, reason, proposed, document_id, pdf_page)
           VALUES (?,?,?,?,?,?,?,?)""",
        (item_type, ref_table, ref_key, title, reason, json.dumps(proposed, ensure_ascii=False), doc_pk, page))


def extra_parcel_values(con) -> list[tuple]:
    """seed/map_reading_parcels.csv → project_parcels 행 값 (project_id, pnu, basis, verified, source_doc_id, pdf_page,
    evidence). 메모(note)는 저장할 열이 없어 근거 문장 뒤에 붙인다. 대표 지번과 같은 필지는 건너뛴다."""
    out = []
    for r in read_csv(EXTRA_MAP_CSV):
        p = con.execute("SELECT id, stage_source_doc_id FROM projects WHERE project_key=?", (r["project_key"],)).fetchone()
        if p is None:
            fail(f"seed/map_reading_parcels.csv: 사업 {r['project_key']}가 DB에 없습니다")
        rep_ = con.execute("SELECT 1 FROM project_parcels WHERE project_id=? AND pnu=? AND basis='representative_only'",
                           (p[0], r["pnu"])).fetchone()
        if rep_:
            continue
        evidence = r["reason"] + (f". {r['note']}" if r.get("note") else "")
        out.append((p[0], r["pnu"], "map_reading", 0, p[1], int(r["map_page"]), evidence))
    return out


def extra_group_reviews(con) -> list[tuple]:
    """seed/map_reading_parcels.csv의 사업마다 parcel_group 검수 1건 (대청마을 묶음 검수와 같은 형식).
    값: (item_type, ref_table, ref_key, title, reason, proposed, document_id, pdf_page)"""
    groups: dict[str, list[dict]] = {}
    for r in read_csv(EXTRA_MAP_CSV):
        groups.setdefault(r["project_key"], []).append(r)
    out = []
    for key, rows in groups.items():
        p = con.execute("SELECT id, name, aliases, stage_source_doc_id FROM projects WHERE project_key=?",
                        (key,)).fetchone()
        if p is None:
            fail(f"seed/map_reading_parcels.csv: 사업 {key}가 DB에 없습니다")
        short = (json.loads(p[2] or "[]") or [p[1]])[0]
        parcels = [{"pnu": r["pnu"], "jibun": r["jibun"], "reason": r["reason"], "note": r.get("note") or None,
                    "confidence": float(r["confidence"]), "checked_by": r.get("checked_by") or None,
                    "decided_by": r.get("decided_by") or None, "decided_at": r.get("decided_at") or None}
                   for r in rows]
        page = int(rows[0]["map_page"])
        jibuns = ", ".join(r["jibun"] for r in rows)
        out.append(("parcel_group", "project_parcels", f"{p[0]}:map_reading",
                    f"{short} — 결정도 대조 필지 {len(rows)}필지 ({jibuns})",
                    "고시 본문에는 없지만 정비구역 결정도 경계 안쪽인 필지 (판정표 3번 강도: 포함된 것으로 보임)",
                    {"current": {"project": p[1], "inclusion": "likely", "basis": "map_reading", "parcels": parcels,
                                 "pdf_page": page},
                     "options": ["approve", "reject"], "editable_fields": ["exclude_pnus"]}, p[3], page))
    return out


def page_text(con, doc_pk: int, pdf_page: int) -> str:
    r = con.execute("SELECT text FROM pages WHERE document_id=? AND pdf_page=?", (doc_pk, pdf_page)).fetchone()
    return r["text"] if r else ""


def facts_for(con, doc_id: str, doc_pk: int, prj: dict) -> list[dict]:
    """사업 카드의 '고시에 적힌 수치'. D1은 필드 추출값, 그 밖은 사업 JSON의 facts."""
    if doc_id == "D1":
        payload = json.loads((EXTRACTIONS / "D1.json").read_text(encoding="utf-8"))["fields"]
        out = []
        for f in D1_FACT_FIELDS:
            r = con.execute("SELECT * FROM extracted_fields WHERE document_id=? AND field=?", (doc_pk, f)).fetchone()
            if r and json.loads(r["value"]) is not None:
                out.append({"label": FIELD_LABELS.get(f, f), "value": json.loads(r["value"]),
                            "unit": payload.get(f, {}).get("unit"), "evidence": r["evidence"], "pdf_page": r["pdf_page"]})
        return out
    return prj.get("facts", [])


def build(con) -> list[dict]:
    rules = load_rules()
    out = []
    bjd = {r["dong_name"]: dict(r) for r in con.execute("SELECT * FROM bjd_codes")}
    anchors = {r["project_key"]: r for r in read_csv(SEED / "project_coords.csv")}
    map_rows = read_csv(MAP_READING_CSV)

    for doc_id in DOC_ORDER:
        path = EXTRACTIONS / f"{doc_id}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data["projects"]:
            continue
        doc = con.execute("SELECT id, title, published_at FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        doc_pk = doc["id"]
        for prj in data["projects"]:
            rule = judge_stage(doc["title"], prj["project_type"], rules)
            if not rule:
                fail(f"{prj['project_key']}: 문서 제목에 맞는 단계 규칙이 없습니다. stage_rules.yaml 확인")
            code, rule_id = rule["code"], rule["id"]
            rj = prj["representative_jibun"]
            dong = bjd.get(rj["dong"]) or fail(f"법정동 코드표에 {rj['dong']}가 없습니다")
            pnu = make_pnu(dong["bjd_code"], rj["main"], rj.get("sub", 0), rj.get("san", False))
            lat, lon, csrc = project_center(con, prj["project_key"], pnu, anchors)
            lu = prj.get("land_use") or {}
            stage_note = rule.get("stage_note", "").format(published=doc["published_at"].replace("-", ".")) or None
            cur = con.execute(
                """INSERT INTO projects(project_key, name, aliases, project_type, track, sgg_code, bjd_code,
                   sub_stage_code, stage_as_of, stage_source_doc_id, stage_rule, area_m2, location_text, land_use,
                   land_use_page, lat, lon, coord_source, sub_status, stage_note, position_note)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (prj["project_key"], prj["name"], json.dumps(prj.get("aliases", []), ensure_ascii=False),
                 prj["project_type"], "unknown", dong["sgg_code"], dong["bjd_code"], code, doc["published_at"],
                 doc_pk, rule_id, prj["area_m2"]["value"], prj.get("location_text"), lu.get("value"),
                 lu.get("pdf_page"), lat, lon, csrc, rule.get("sub_status"), stage_note, rule.get("position_note")))
            pid = cur.lastrowid
            if prj.get("stage_candidate") and prj["stage_candidate"] != code:
                review(con, "stage_uncertain", "projects", str(pid), f"{prj['name']} — 단계 판정",
                       f"추출 후보 {prj['stage_candidate']}와 규칙 {rule_id} 결과 {code}가 다름 (규칙 결과를 씀)",
                       {"current": {"rule": rule_id, "code": code, "candidate": prj["stage_candidate"]},
                        "options": ["approve", "reject"], "editable_fields": []}, doc_pk,
                       prj["stage_evidence"]["pdf_page"])

            se = prj["stage_evidence"]
            con.execute(
                """INSERT INTO project_stage_history(project_id, sub_stage_code, entered_at, source_doc_id, basis,
                   pdf_page, evidence) VALUES (?,?,?,?,?,?,?)""",
                (pid, code, doc["published_at"], doc_pk, "gosi", se["pdf_page"], se["evidence"]))
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
            for i, f in enumerate(facts_for(con, doc_id, doc_pk, prj), start=1):
                con.execute(
                    """INSERT INTO project_facts(project_id, seq, label, value, unit, evidence, evidence_ok,
                       source_doc_id, pdf_page) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (pid, i, f["label"], json.dumps(f["value"], ensure_ascii=False), f.get("unit"), f["evidence"],
                     int(evidence_in(f["evidence"], page_text(con, doc_pk, f["pdf_page"]))), doc_pk, f["pdf_page"]))
            con.execute(
                """INSERT INTO doc_locations(document_id, pnu, bjd_code, sgg_code, method, jibun_text, pdf_page,
                   evidence, confidence) VALUES (?,?,?,?,?,?,?,?,?)""",
                (doc_pk, pnu, dong["bjd_code"], dong["sgg_code"], "representative", rj["text"], rj["pdf_page"],
                 rj["evidence"], 0.6))
            con.execute(
                """INSERT INTO project_parcels(project_id, pnu, basis, verified, source_doc_id, pdf_page, evidence)
                   VALUES (?,?,?,?,?,?,?)""", (pid, pnu, "representative_only", 0, doc_pk, rj["pdf_page"],
                                               rj["evidence"]))
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

            n_map = 0
            if prj["project_key"] == MAP_READING_PROJECT and map_rows:
                parcels = []
                for r in map_rows:
                    if r["pnu"] == pnu:
                        continue
                    con.execute(
                        """INSERT INTO project_parcels(project_id, pnu, basis, verified, source_doc_id, pdf_page,
                           evidence) VALUES (?,?,?,?,?,?,?)""",
                        (pid, r["pnu"], "map_reading", 0, doc_pk, int(r["map_page"]), r["reason"]))
                    parcels.append({"pnu": r["pnu"], "jibun": r["jibun"], "reason": r["reason"],
                                    "confidence": float(r["confidence"]), "checked_by": r.get("checked_by") or None})
                n_map = len(parcels)
                page = int(map_rows[0]["map_page"])
                review(con, "parcel_group", "project_parcels", f"{pid}:map_reading",
                       f"{short} — 구역 지도 대조 후보 {n_map}필지",
                       "고시에 지번 조서가 없어 관리지역 결정도와 지적도를 맞대 본 후보 (판정표 3번 강도: 포함된 것으로 보임)",
                       {"current": {"project": prj["name"], "inclusion": "likely", "basis": "map_reading",
                                    "parcels": parcels, "pdf_page": page},
                        "options": ["approve", "reject"], "editable_fields": ["exclude_pnus"]}, doc_pk, page)
            out.append({"project_id": pid, "key": prj["project_key"], "stage": code, "rule": rule_id, "pnu": pnu,
                        "coord": lat is not None, "map": n_map})
    for v in extra_parcel_values(con):
        con.execute("""INSERT INTO project_parcels(project_id, pnu, basis, verified, source_doc_id, pdf_page, evidence)
                       VALUES (?,?,?,?,?,?,?)""", v)
        log(f"build_projects: 결정도 대조 필지 사업 {v[0]} {v[1]} (map_reading, 확인 전)")
    return out


def main() -> None:
    setup_stdout()
    con = connect_rw()
    con.execute("DELETE FROM review_queue WHERE item_type IN ('parcel_inclusion','parcel_group','stage_uncertain')")
    for t in ("project_documents", "project_parcels", "project_facts", "doc_locations", "deadlines", "related_history",
              "project_stage_history", "projects"):
        con.execute(f"DELETE FROM {t}")
    res = build(con)
    con.commit()
    con.close()
    for r in res:
        log(f"build_projects: {r['key']} 단계 {r['stage']}({r['rule']}) 대표 필지 {r['pnu']} "
            f"좌표 {'있음' if r['coord'] else '없음(500m 판정 생략)'}" + (f", 지도 대조 후보 {r['map']}필지" if r["map"] else ""))


if __name__ == "__main__":
    main()
