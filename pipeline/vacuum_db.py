"""db/propedia.db를 VACUUM한다 (P15 0단계, 멱등).

P13 patch_coords가 land_cache·projects의 지오코더 좌표를 필지 중심점으로 덮어쓸 때 VACUUM을 하지 않아,
옛 좌표 바이트가 DB 파일의 페이지 빈 공간에 남아 있었다 (행 데이터에는 없음). VACUUM으로 파일을 다시 쓰고,
'vworld-geocoder' 바이트가 0건인지 확인한다. 행 내용은 바뀌지 않는다.

사용: python -m pipeline.vacuum_db
"""
import sys

from pipeline.common import DB_PATH, fail, log, setup_stdout, sha256, vacuum_db

MARK = b"vworld-geocoder"


def residue(path=DB_PATH) -> int:
    return path.read_bytes().count(MARK)


def main() -> int:
    setup_stdout()
    before, h0 = residue(), sha256(DB_PATH)
    if before == 0:          # VACUUM은 파일 머리의 변경 횟수를 바꿔 바이트가 달라진다 → 할 일이 없으면 건드리지 않음 (멱등)
        log(f"db/propedia.db 'vworld-geocoder' 바이트 0건 · 그대로 둠 (sha256 {h0[:16]})")
        return 0
    vacuum_db()
    after, h1 = residue(), sha256(DB_PATH)
    log(f"db/propedia.db 'vworld-geocoder' 바이트 {before} → {after}건 · sha256 {h0[:16]} → {h1[:16]}")
    if after:
        fail("VACUUM 뒤에도 지오코더 표시가 남아 있습니다 (행 데이터에 있음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
