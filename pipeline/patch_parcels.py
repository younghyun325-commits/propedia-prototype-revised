"""DB 사업 필지(project_parcels)만 seed 값으로 갱신 (P13.5). 네트워크·../data 없이 동작, 멱등.

원본 PDF(../data)가 없는 PC에서는 run_all을 돌릴 수 없으므로, seed가 바뀐 지도 대조 필지만 db/propedia.db에 옮긴다.
원본 PC에서 run_all을 돌리면 같은 값이 나온다:
  - project_parcels(map_reading) ← build_projects.build()가 seed/daecheong_map_reading.csv(대청마을)와
    seed/map_reading_parcels.csv(그 밖, extra_parcel_values)로 넣는 행. 여기서도 같은 규칙·같은 함수를 쓴다.
  - review_queue(parcel_group, seed/map_reading_parcels.csv의 사업) ← review_queue.build() 맨 끝에서
    build_projects.extra_group_reviews()로 넣는 행. 둘 다 마지막 id를 받으므로 id까지 같다.
대표 지번 행(representative_only)과 그 밖의 열·표는 건드리지 않는다.

순서: db/propedia.db → build/propedia.db.bak 복사 → 시연 15건 판정 기록 → 갱신 → 다시 판정 → 전·후 표.
     seed에 바뀐 필지가 없는 주소의 판정이 하나라도 바뀌면 .bak으로 되돌리고 종료 코드 1.

사용: python -m pipeline.patch_parcels
"""
import json
import shutil
import sqlite3
import sys

from pipeline.build_projects import (MAP_READING_CSV, MAP_READING_PROJECT, EXTRA_MAP_CSV, extra_group_reviews,
                                     extra_parcel_values, read_csv)
from pipeline.common import BUILD, DB_PATH, log, setup_stdout, sha256, vacuum_db
from pipeline.patch_coords import judgments

BAK = BUILD / "propedia.db.bak"
COLS = "project_id, pnu, basis, verified, source_doc_id, pdf_page, evidence"


def expected_map_rows(con) -> dict[tuple, tuple]:
    """build_projects.build()와 같은 규칙으로 map_reading 행 전체를 만든다 {(project_id, pnu): 행 값}."""
    out = {}
    p = con.execute("SELECT id, stage_source_doc_id FROM projects WHERE project_key=?", (MAP_READING_PROJECT,)).fetchone()
    if p is not None:
        reps = {r[0] for r in con.execute(
            "SELECT pnu FROM project_parcels WHERE project_id=? AND basis='representative_only'", (p[0],))}
        for r in read_csv(MAP_READING_CSV):
            if r["pnu"] in reps:
                continue
            out[(p[0], r["pnu"])] = (p[0], r["pnu"], "map_reading", 0, p[1], int(r["map_page"]), r["reason"])
    for v in extra_parcel_values(con):
        out[(v[0], v[1])] = v
    return out


def apply(con) -> dict[str, int]:
    n = {"insert": 0, "update": 0, "delete": 0, "review": 0}
    want = expected_map_rows(con)
    have = {(r[0], r[1]): tuple(r) for r in con.execute(
        f"SELECT {COLS} FROM project_parcels WHERE basis='map_reading'")}
    for k, v in want.items():
        if k not in have:
            con.execute(f"INSERT INTO project_parcels({COLS}) VALUES (?,?,?,?,?,?,?)", v)
            n["insert"] += 1
        elif have[k] != v:
            con.execute("""UPDATE project_parcels SET basis=?, verified=?, source_doc_id=?, pdf_page=?, evidence=?
                           WHERE project_id=? AND pnu=?""", (*v[2:], v[0], v[1]))
            n["update"] += 1
    for k in have.keys() - want.keys():
        con.execute("DELETE FROM project_parcels WHERE project_id=? AND pnu=? AND basis='map_reading'", k)
        n["delete"] += 1

    dc = con.execute("SELECT id FROM projects WHERE project_key=?", (MAP_READING_PROJECT,)).fetchone()
    keep = {f"{dc[0]}:map_reading"} if dc else set()
    for item_type, ref_table, ref_key, title, reason, proposed, doc_pk, page in extra_group_reviews(con):
        keep.add(ref_key)
        val = (ref_table, title, reason, json.dumps(proposed, ensure_ascii=False), doc_pk, page)
        cur = con.execute("""SELECT ref_table, title, reason, proposed, document_id, pdf_page FROM review_queue
                             WHERE item_type=? AND ref_key=?""", (item_type, ref_key)).fetchone()
        if cur is None:
            con.execute("""INSERT INTO review_queue(item_type, ref_key, ref_table, title, reason, proposed, document_id,
                           pdf_page) VALUES (?,?,?,?,?,?,?,?)""", (item_type, ref_key, *val))
            n["review"] += 1
        elif tuple(cur) != val:
            con.execute("""UPDATE review_queue SET ref_table=?, title=?, reason=?, proposed=?, document_id=?, pdf_page=?
                           WHERE item_type=? AND ref_key=?""", (*val, item_type, ref_key))
            n["review"] += 1
    for (ref_key,) in con.execute("SELECT ref_key FROM review_queue WHERE item_type='parcel_group'").fetchall():
        if ref_key not in keep:
            con.execute("DELETE FROM review_queue WHERE item_type='parcel_group' AND ref_key=?", (ref_key,))
            n["review"] += 1
    return n


def fmt(j: dict) -> str:
    if j["status"] != "ok":
        return j["status"]
    parts = [f"포함 {pid}:{inc}" for pid, inc in j["included"]]
    parts += [f"주변 {pid} {j['nearby_m'][pid]}m" for pid in j["nearby"]]
    parts += [f"법정동 {pid}" for pid in j["dong_projects"]]
    return ", ".join(parts) or "사업 없음"


def main() -> int:
    setup_stdout()
    BAK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB_PATH, BAK)
    log(f"백업 build/propedia.db.bak (sha256 {sha256(BAK)[:16]})")
    con = sqlite3.connect(DB_PATH)
    seed_pnus = {r["pnu"] for r in read_csv(EXTRA_MAP_CSV)}
    con.close()

    before = judgments(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    n = apply(con)
    con.commit()
    con.close()
    after = judgments(DB_PATH)

    log("주소 | PNU 변경 대상 | 전 | 후")
    bad = []
    con = sqlite3.connect(DB_PATH)
    pnu_of = dict(con.execute("SELECT addr_id, pnu FROM demo_addresses").fetchall())
    con.close()
    for aid in sorted(before):
        touched = pnu_of.get(aid) in seed_pnus
        same = {k: v for k, v in before[aid].items() if k != "nearby_m"} == \
               {k: v for k, v in after[aid].items() if k != "nearby_m"}
        log(f"{aid} | {'예' if touched else '-'} | {fmt(before[aid])} | {fmt(after[aid])}"
            + ("" if same else "  ← 바뀜"))
        if not same and not touched:
            bad.append(aid)
        if touched and not any(inc == "likely" for _, inc in after[aid]["included"]):
            bad.append(aid)              # seed에 넣은 필지는 '포함된 것으로 보임'이어야 한다
    if bad:
        shutil.copy2(BAK, DB_PATH)
        log(f"seed와 상관없는 주소의 판정이 바뀜 {bad} → build/propedia.db.bak으로 되돌림")
        return 1
    log(f"project_parcels 추가 {n['insert']} · 수정 {n['update']} · 삭제 {n['delete']} / 검수 행 변경 {n['review']}")
    vacuum_db()          # 덮어쓴 옛 행 바이트를 남기지 않는다 (P15 0단계)
    log(f"db/propedia.db sha256 {sha256(DB_PATH)[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
