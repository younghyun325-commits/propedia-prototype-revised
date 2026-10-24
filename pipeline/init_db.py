"""db/propedia.db를 지우고 db/schema.sql로 새로 만든다 (agents.md §8-9)."""
from pipeline.common import DB_PATH, ROOT, connect_rw, log, setup_stdout


def main() -> None:
    setup_stdout()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-journal", "-wal", "-shm"):
        p = DB_PATH.with_name(DB_PATH.name + suffix)
        if p.exists():
            p.unlink()
    con = connect_rw()
    con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    con.commit()
    n = con.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    con.close()
    log(f"init_db: 테이블 {n}개 생성 ({DB_PATH.relative_to(ROOT)})")


if __name__ == "__main__":
    main()
