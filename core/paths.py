"""실행 중에 읽는 데이터 파일의 위치 (P20-B). 표준 라이브러리만.

**Vercel은 프로젝트 루트 `public/`을 CDN이 플랫폼 수준에서 서빙하고 Python 함수 묶음에는 넣지 않는다.**
Vercel FastAPI 문서는 `public/` 절에서 CDN 서빙만 설명하고("Do not mount the `public/` directory with
`app.mount()`. Vercel handles it at the platform level."), '묶음에 남겨 실행 중에 읽을 수 있다'는 보장은
`app.mount()`·`app.frontend()`로 승격된 디렉터리에만 적는다("Promoted source directories are kept in the
function bundle by default so the app can read from them at runtime"). `api/index.py`의 mount는
`VERCEL != "1"`일 때만 실행되므로 배포본에는 승격도 묶음 포함도 없다.

관찰 (운영 2026-11-11, 커밋 8ae7582): `/data/layers/manifest.json`은 CDN에서 200인데
`/api/v1/map/manifest`는 503, `/api/v1/map/wms/...`는 경계 bbox가 없어 400, 필지 응답의 `ref_zones`는 0건.
반면 `public/` 밖의 `db/*.db`는 함수에서 그대로 읽힌다(`/api/v1/health` 200).

그래서 **서버가 실행 중에 읽는 지도 파일은 `public/` 밖 `data/server/`에 같은 내용으로 두고 여기만 읽는다.**
`pipeline/sync_server_data.py`가 `public/data`에서 복사하고, `tests/test_server_data.py`가 두 사본이 같은지와
`core/`가 `public/`을 읽지 않는지를 확인한다.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_DATA = ROOT / "data" / "server"       # 서버가 읽는 곳 (public/ 밖, 함수 묶음에 들어간다)
PUBLIC_ENV = "PROPEDIA_PUBLIC_DIR"


def public_dir() -> Path:
    """CDN이 서빙하는 폴더. 로컬 정적 서빙·빌드 스크립트에서만 쓴다.

    환경변수 `PROPEDIA_PUBLIC_DIR`로 바꿀 수 있다 — 없는 경로를 주면 배포본과 같은 조건
    (함수가 `public/`을 읽지 못함)이 되어 `tests/test_server_data.py`가 그 조건에서 API를 점검한다.
    """
    v = os.environ.get(PUBLIC_ENV)
    return Path(v) if v else ROOT / "public"


def layers_dir() -> Path:
    return SERVER_DATA / "layers"


def base_dir() -> Path:
    return SERVER_DATA / "base"
