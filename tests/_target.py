"""화면 점검 도구(ui_check·ui_check_map·demo_map_run) 공통: 점검 대상 주소, 키 가림, 스크린샷 이름 (P20).

- 대상이 localhost·127.0.0.1이면 로컬, 아니면 원격(운영·Preview).
- 출력 가림: 로컬 .env 값(pipeline.peek 규칙) + 브이월드 타일 주소의 키 자리(WMTS 경로·KEY=).
  운영 키는 로컬 .env에 없으므로 주소 모양으로 가리는 정규식이 실제로 가린다.
- 원격 점검 스크린샷은 prod_ 접두를 붙여 로컬 스크린샷을 덮어쓰지 않는다.
- 캡처는 기본으로 tmp/<도구>/<타임스탬프>/ 에 쓴다(.gitignore). docs/screens/는 --update-screens를 주고
  실패가 0건일 때만 그 실행의 캡처로 갱신한다 (불완전한 실행이 기록용 캡처를 덮어쓰지 않게, P20).
"""
import re
import shutil
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import peek  # noqa: E402

LOCAL_HOSTS = {"localhost", "127.0.0.1"}
KEY_RE = re.compile(r"(/req/wmts/1\.0\.0/)[^/]+/")
WMS_KEY_RE = re.compile(r"((?:KEY|apikey|key)=)[^&\s\"']+", re.I)
_ENV = None


def is_remote(base: str) -> bool:
    return (urllib.parse.urlsplit(base).hostname or "") not in LOCAL_HOSTS


def mask_text(s: str) -> str:
    global _ENV
    if _ENV is None:
        _ENV = peek.read_env(ROOT / ".env")
    s = WMS_KEY_RE.sub(r"\1***", KEY_RE.sub(r"\1***/", s or ""))
    return peek.mask(s, _ENV)[0]


def shot_name(name: str, remote: bool) -> str:
    return f"prod_{name}" if remote else name


SCREENS = ROOT / "docs" / "screens"


def run_dir(tool: str) -> Path:
    """이번 실행의 캡처 폴더 tmp/<tool>/<타임스탬프>/ (커밋 안 함)"""
    d = ROOT / "tmp" / tool / time.strftime("%Y%m%d-%H%M%S")
    d.mkdir(parents=True, exist_ok=True)
    return d


def publish_shots(src: Path, update: bool, n_fail: int) -> None:
    """--update-screens이고 실패 0건이면 src의 캡처를 docs/screens/로 복사. 아니면 갱신하지 않은 이유를 한 줄 출력."""
    files = sorted(src.glob("*.png"))
    where = src.relative_to(ROOT).as_posix() if src.is_relative_to(ROOT) else str(src)
    print(f"캡처 {len(files)}장: {where}/")
    if not update:
        print("docs/screens/ 갱신 안 함: --update-screens 없음")
    elif n_fail:
        print(f"docs/screens/ 갱신 안 함: 실패 {n_fail}건")
    elif not files:
        print("docs/screens/ 갱신 안 함: 캡처 없음")
    else:
        SCREENS.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(f, SCREENS / f.name)
        print(f"docs/screens/ 갱신: {len(files)}장")
