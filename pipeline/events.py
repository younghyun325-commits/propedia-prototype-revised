"""문서 1건씩 투입 순서별 사업 상태 변화 → change_events (agents.md §8-12).

step k까지 들어온 문서만으로 사업 상태(사업 목록, 단계, 기한, 소속 문서)를 계산하고,
step k-1 상태와 달라진 것만 기록한다. 새 사업에는 doc_attached를 넣지 않는다.
"""
import json
from datetime import datetime

from pipeline.common import connect_rw, log, setup_stdout


def state(con, k: int) -> dict:
    docs = {r["id"] for r in con.execute("SELECT id FROM documents WHERE ingest_step <= ?", (k,))}
    out = {}
    for p in con.execute("SELECT id, name FROM projects ORDER BY id"):
        pdocs = {r["document_id"] for r in
                 con.execute("SELECT document_id FROM project_documents WHERE project_id=?", (p["id"],))} & docs
        if not pdocs:
            continue
        hist = [r for r in con.execute(
            "SELECT sub_stage_code, entered_at, source_doc_id FROM project_stage_history WHERE project_id=? "
            "ORDER BY entered_at", (p["id"],)) if r["source_doc_id"] in docs]
        dls = {(r["kind"], r["title"], r["due_on"]) for r in con.execute(
            "SELECT kind, title, due_on, source_doc_id FROM deadlines WHERE project_id=?", (p["id"],))
            if r["source_doc_id"] in docs}
        out[p["id"]] = {"name": p["name"], "stage": hist[-1]["sub_stage_code"] if hist else None,
                        "deadlines": dls, "docs": pdocs}
    return out


def build(con) -> dict[int, int]:
    con.execute("DELETE FROM change_events")
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    steps = [r["ingest_step"] for r in con.execute("SELECT DISTINCT ingest_step FROM documents ORDER BY ingest_step")]
    counts = {}
    prev = {}
    for k in steps:
        doc_id = con.execute("SELECT id FROM documents WHERE ingest_step=?", (k,)).fetchone()["id"]
        cur = state(con, k)
        events = []
        for pid, s in cur.items():
            old = prev.get(pid)
            if old is None:
                events.append((pid, "new_project", None, {"name": s["name"], "stage": s["stage"]}))
            else:
                if old["stage"] != s["stage"]:
                    events.append((pid, "stage_change", {"stage": old["stage"]}, {"stage": s["stage"]}))
                for d in sorted(s["docs"] - old["docs"]):
                    events.append((pid, "doc_attached", None, {"document_id": d}))
            old_dl = old["deadlines"] if old else set()
            for kind, title, due in sorted(s["deadlines"] - old_dl):
                events.append((pid, "deadline_added", None, {"kind": kind, "title": title, "due_on": due}))
        for pid, et, before, after in events:
            con.execute(
                """INSERT INTO change_events(step, project_id, event_type, before, after, source_doc_id, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (k, pid, et, json.dumps(before, ensure_ascii=False) if before else None,
                 json.dumps(after, ensure_ascii=False), doc_id, now))
        counts[k] = len(events)
        prev = cur
    return counts


def main() -> None:
    setup_stdout()
    con = connect_rw()
    counts = build(con)
    con.commit()
    con.close()
    log(f"events: 투입 단계별 이벤트 수 {counts}")


if __name__ == "__main__":
    main()
