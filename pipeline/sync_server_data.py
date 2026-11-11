"""서버가 실행 중에 읽는 지도 파일을 `public/data` → `data/server`로 복사한다 (P20-B). 네트워크 없음.

**왜**: Vercel은 프로젝트 루트 `public/`을 CDN이 플랫폼 수준에서 서빙하고 Python 함수 묶음에는 넣지 않는다
(근거·운영 관찰은 `core/paths.py` 머리말). 그래서 브라우저가 받는 파일은 `public/data`에 그대로 두고,
**서버가 읽는 9개만** `public/` 밖 `data/server/`에 같은 내용으로 둔다. `core/`는 `data/server/`만 읽는다.

- 브라우저만 쓰는 큰 레이어(pois_*·apartments·bus_*·schools·stations)는 복사하지 않는다 (함수 묶음을 키우지 않기 위해).
- 바이트가 다를 때만 쓴다 (멱등 — 다시 실행해도 git이 깨끗하다).
- `public/data`를 만드는 스크립트(build_map_base·build_map_layers·import_reference·fetch_pois)가 끝에서 이 함수를 부른다.
- `tests/test_server_data.py`가 두 사본이 같은지, `core/`가 `public/`을 읽지 않는지 확인한다.

사용:
  python -m pipeline.sync_server_data            # 복사 (바뀐 것만)
  python -m pipeline.sync_server_data --check     # 비교만, 다르면 종료 코드 1
"""
import argparse
import sys

from core.paths import SERVER_DATA
from pipeline.common import PUBLIC, log, setup_stdout, sha256

SRC = PUBLIC / "data"

# (하위 폴더, 파일 이름) — core/map.py·core/refzones.py가 읽는 것 전부
FILES = [
    ("layers", "manifest.json"),                 # core/map.map_manifest, timeline
    ("layers", "propedia_projects.geojson"),     # core/map._source_pages
    ("layers", "propedia_impact.geojson"),
    ("layers", "propedia_parcels.geojson"),
    ("layers", "propedia_regulations.geojson"),
    ("layers", "ref_seoulplan.geojson"),         # core/refzones
    ("layers", "ref_uije.geojson"),
    ("base", "gangnam.geojson"),                 # core/map.map_manifest, gangnam_bbox (WMS 허용 범위)
    ("base", "bjd.geojson"),
]


def sync(check: bool = False, quiet: bool = False) -> list[str]:
    """`data/server/`를 `public/data/`와 맞춘다. 다른(또는 없는) 파일 이름 목록을 돌려준다."""
    diff: list[str] = []
    missing: list[str] = []
    for sub, name in FILES:
        src, dst = SRC / sub / name, SERVER_DATA / sub / name
        if not src.exists():
            missing.append(f"{sub}/{name}")
            continue
        want = src.read_bytes()
        if dst.exists() and dst.read_bytes() == want:
            continue
        diff.append(f"{sub}/{name}")
        if not check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(want)
    if missing:
        log(f"[건너뜀] public/data에 없는 파일: {', '.join(missing)} (빌드 스크립트를 먼저 실행)")
    if not quiet:
        for sub, name in FILES:
            dst = SERVER_DATA / sub / name
            if dst.exists():
                log(f"  {sub}/{name}: {dst.stat().st_size:,} B sha256 {sha256(dst)[:8]}")
        total = sum((SERVER_DATA / s / n).stat().st_size for s, n in FILES if (SERVER_DATA / s / n).exists())
        log(f"data/server 합계 {total:,} B ({total / 1024 / 1024:.2f} MB)")
    return diff + missing


def main() -> int:
    setup_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="복사하지 않고 비교만 한다 (다르면 종료 코드 1)")
    args = ap.parse_args()
    diff = sync(check=args.check)
    if args.check:
        if diff:
            log(f"[다름] {', '.join(diff)} → python -m pipeline.sync_server_data")
            return 1
        log("data/server가 public/data와 같습니다")
        return 0
    log(f"복사 {len(diff)}개" + (f": {', '.join(diff)}" if diff else " (이미 같음)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
