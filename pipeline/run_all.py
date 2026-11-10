"""DB 전체 재빌드 (agents.md §8-14). 네트워크를 쓰지 않는다.

init_db → load_seed → load_extractions → build_projects → events → review_queue → meta
(resolve_addresses·geocode는 따로 실행해 seed에 결과를 남긴다. 평가는 python -m evals.run_eval)
"""
from datetime import datetime

from pipeline import build_projects, events, init_db, load_extractions, load_seed, review_queue
from pipeline.common import connect_rw, log, setup_stdout

COVERAGE_NOTE = ("프리토타입: 강남구. 고시·계획 문서 10종(D1 한양7차 재건축 정비계획(안) 공람, D2 2030 생활권계획 일부, "
                 "D3 2030 정비기본계획 재건축 부문 일부, D4 2040 서울도시기본계획 일부, D5~D7 토지거래허가구역·"
                 "조정대상지역 지정 공고, D8 국토교통부 보도참고자료, D9 대청마을 북측 모아타운 관리계획(안) 공람, "
                 "D10 대치동 506 개발행위허가 제한)만 반영했습니다. 토지 정보는 브이월드에서 실시간으로 불러옵니다. "
                 "2030 생활권계획(2018)은 참고로만 보여줍니다.")

# P3 완료 확인 SQL (agents.md §18). P10부터 사업이 2건(한양7차 재건축, 대청마을 모아타운)이다.
P3_SQL = [
    ("SELECT project_key, sub_stage_code, stage_as_of FROM projects ORDER BY id",
     "apgujeong-6-1-hanyang7 | RB02 | 2026-10-06 / ilwon-daecheong-north-moatown | MT01 | 2026-04-17"),
    ("SELECT due_on FROM deadlines ORDER BY project_id", "2026-11-06 / 2026-05-01"),
    ("SELECT step, event_type FROM change_events ORDER BY step, id",
     "4 | new_project / 4 | deadline_added / 9 | new_project / 9 | deadline_added"),
    ("SELECT item_type, ref_key FROM review_queue WHERE item_type='parcel_inclusion' ORDER BY id",
     "parcel_inclusion | 1:1168011000105270000 / parcel_inclusion | 2:1168011400106190000"),
    ("SELECT pnu, basis, verified FROM project_parcels WHERE basis='representative_only' ORDER BY project_id",
     "1168011000105270000 | representative_only | 0 / 1168011400106190000 | representative_only | 0"),
    ("SELECT project_id, count(*), sum(verified) FROM project_parcels WHERE basis='map_reading' GROUP BY project_id",
     "1 | 1 | 0 / 2 | 16 | 0"),        # 1 = 압구정동 528 결정도 대조 (P13.5, seed/map_reading_parcels.csv)
]


def sql_rows(con, sql: str) -> str:
    return " / ".join(" | ".join(str(v) for v in tuple(r)) for r in con.execute(sql).fetchall())


def main() -> None:
    setup_stdout()
    init_db.main()
    load_seed.main()
    con = connect_rw()
    stats = load_extractions.load(con)
    con.commit()
    for s in stats:
        if not s.get("missing"):
            log(f"load_extractions: {s['doc']} 항목 {s['items']} 근거 {s['ok']}/{s['total']}")
    con.close()
    build_projects.main()
    events.main()
    review_queue.main()

    con = connect_rw()
    as_of = con.execute("SELECT max(published_at) FROM documents").fetchone()[0]
    meta = {"build_at": datetime.now().astimezone().isoformat(timespec="seconds"), "as_of": as_of,
            "schema_version": "3", "coverage_note": COVERAGE_NOTE}
    for k, v in meta.items():
        con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?,?)", (k, v))
    con.commit()
    log(f"meta: as_of={as_of}, build_at={meta['build_at']}")
    log("── P3 완료 확인 SQL ──")
    for sql, expect in P3_SQL:
        log(f"{sql}\n   → {sql_rows(con, sql)}   (기대: {expect})")
    con.close()


if __name__ == "__main__":
    main()
