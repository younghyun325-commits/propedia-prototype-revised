"""meta.patched_at 기록을 시작한다 (P20, 1회용·멱등).

P20 전까지 patch_coords·patch_parcels는 DB를 고쳐도 meta에 시각을 남기지 않아, /api/v1/health의 build_at(run_all 시각)만
보였다. 이 스크립트는 db/propedia.db를 마지막으로 커밋한 git 커밋의 시각·해시를 patched_at·patched_by로 한 번 적는다.
이미 patched_at이 있으면 건드리지 않는다. 이후 갱신은 patch_* 스크립트가 바뀐 행이 있을 때 직접 적는다(common.mark_patched).

사용: python -m pipeline.mark_patched
"""
import sqlite3
import subprocess
import sys

from pipeline.common import DB_PATH, ROOT, fail, log, mark_patched, setup_stdout, sha256, vacuum_db


def main() -> int:
    setup_stdout()
    con = sqlite3.connect(str(DB_PATH))
    try:
        row = con.execute("SELECT value FROM meta WHERE key='patched_at'").fetchone()
    finally:
        con.close()
    if row:
        log(f"meta patched_at 이미 있음 ({row[0]}) · 그대로 둠")
        return 0
    out = subprocess.run(["git", "log", "-1", "--format=%h %cI", "--", "db/propedia.db"],
                         cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if not out:
        fail("db/propedia.db의 git 커밋을 찾지 못했습니다")
    h, at = out.split(" ", 1)
    mark_patched(f"기록 시작: 마지막 DB 커밋 {h}", at=at)
    vacuum_db()
    log(f"meta patched_at {at} · patched_by '기록 시작: 마지막 DB 커밋 {h}' · sha256 {sha256(DB_PATH)[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
